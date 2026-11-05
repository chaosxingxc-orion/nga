FROM sha256:8190b3ec51929baca2388452039ccf05d681c01b7c91cc55dd1e7ac5570a76b7
COPY source/ /opt/nga/source/
COPY third-party/ /opt/nga/third-party/
COPY components/ /opt/nga/components/
COPY adapter.py panel_score.py panel_export.py test_panel_bridge.py entrypoint.sh SOURCE-MANIFEST.json schema.json /opt/nga/
RUN python3 -B -P -c "import json,hashlib,pathlib; m=json.load(open('/opt/nga/SOURCE-MANIFEST.json')); [(lambda p,h: (_ for _ in ()).throw(ValueError(str(p))) if hashlib.sha256(p.read_bytes()).hexdigest()!=h else None)(pathlib.Path(x['image']),x['sha256']) for x in m['files']]" && chmod 555 /opt/nga/entrypoint.sh
ENTRYPOINT ["/opt/nga/entrypoint.sh"]
