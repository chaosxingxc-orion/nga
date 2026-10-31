"""CPU simulation of the Q-host transport contract, not a Torch/NPU adapter."""
from dataclasses import dataclass
import hashlib
import math


@dataclass(frozen=True)
class Metadata:
    shape: tuple
    stride: tuple
    dtype: str = 'float32'
    byteorder: str = 'little'
    storage_offset: int = 0
    external_aliases: int = 0
    device: str = 'npu:0'
    device_format: str = 'ND'

    def validate(self):
        if (type(self.shape) is not tuple or not self.shape or
            any(type(x) is not int or x <= 0 for x in self.shape)):
            raise ValueError('positive integer shape required')
        stride = []
        running = 1
        for size in reversed(self.shape):
            stride.append(running)
            running *= size
        if self.stride != tuple(reversed(stride)):
            raise ValueError('only canonical contiguous layout supported')
        if (self.dtype != 'float32' or self.byteorder != 'little' or
            self.storage_offset != 0 or self.external_aliases != 0 or
            self.device_format != 'ND' or not self.device.startswith('npu:')):
            raise ValueError('unsupported dtype, offset, alias, device or format')
        return math.prod(self.shape) * 4


class HostStage:
    """Own raw bytes only; callbacks must complete synchronously.

    This fixture cannot inspect device aliases or streams. Metadata is supplied
    by the caller, so its truth requires separate runtime verification.
    """
    def __init__(self, metadata, source, copy_to_host=bytes):
        expected = metadata.validate()
        if not isinstance(source, (bytes, bytearray)) or len(source) != expected:
            raise ValueError('exact whole-storage bytes required')
        self.metadata = metadata
        self.state = 'copying'
        self._host = None
        self.digest = hashlib.sha256(source).hexdigest()
        try:
            copied = copy_to_host(source)
            if not isinstance(copied, (bytes, bytearray)) or len(copied) != expected:
                raise ValueError('invalid host copy')
            self._host = bytearray(copied)  # force owned staging, no view
            if hashlib.sha256(self._host).hexdigest() != self.digest:
                raise ValueError('host copy changed bytes')
            self.state = 'staged'
        except BaseException:
            self.close('failed')
            raise

    def close(self, state='closed'):
        if self._host is not None:
            self._host.clear()
            self._host = None
        self.state = state

    def restore(self, copy_to_device):
        """Callback returns (raw restored bytes, observed Metadata).

        Validation failure is terminal. The simulated host buffer is released;
        a real adapter must additionally free any partial device allocation.
        """
        if self.state != 'staged':
            raise ValueError('stage is not available for restoration')
        self.state = 'restoring'
        try:
            restored, actual = copy_to_device(bytes(self._host), self.metadata)
            if actual != self.metadata:
                raise ValueError('restored metadata differs')
            actual.validate()
            if not isinstance(restored, (bytes, bytearray)) or len(restored) != len(self._host):
                raise ValueError('restored storage length differs')
            if bytes(restored) != bytes(self._host):
                raise ValueError('restored bytes differ')
            result = bytes(restored)
            self.close('restored')
            return result, actual
        except BaseException:
            self.close('failed')
            raise
