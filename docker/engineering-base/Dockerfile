FROM sha256:27b2f9a84cbc3bc3eca95bb5ded98431f1a87ca8f0ef5d895970f4060ec4f325
COPY source/ /opt/nga/source/
COPY third-party/ /opt/nga/third-party/
COPY components/ /opt/nga/components/
COPY adapter.py panel_score.py panel_score_load.py panel_export.py test_panel_bridge.py test_panel_score_load.py entrypoint.sh SOURCE-MANIFEST.json schema.json /opt/nga/
RUN python3 -B -P -c "import json,hashlib,pathlib; m=json.load(open('/opt/nga/SOURCE-MANIFEST.json')); [(lambda p,h: (_ for _ in ()).throw(ValueError(str(p))) if hashlib.sha256(p.read_bytes()).hexdigest()!=h else None)(pathlib.Path(x['image']),x['sha256']) for x in m['files']]" && chmod 555 /opt/nga/entrypoint.sh
ENTRYPOINT ["/opt/nga/entrypoint.sh"]
