import json
from prolog_ai import run_nlcd, run_rex, run_aiq, run_scds, run_ssm

def show(name, result):
    print(f"=== {name}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

# text = "피터 파커는 책임감이 강하지만 자신감이 부족한 고등학생이다. 벤 삼촌의 영향을 크게 받았으며 폭력을 싫어한다."
# show("NLCD", run_nlcd(text))
#
# manuscript = "1장 계약\n모든 주문은 정령과의 계약을 통해서만 발현된다. 계약 없는 마법은 존재하지 않는다.\n2장 시험\n리아는 정령과 계약을 맺고 첫 주문을 외웠다."
# show("REX", run_rex(manuscript))
# show("AIQ", run_aiq("리아는 어떻게 첫 주문을 외울 수 있었나요?", manuscript, scope="project"))
# show("SSM", run_ssm(manuscript))

event = {"character_ids": ["char_001"], "content": "피터는 계약 없이 즉흥 마법을 써서 강도를 잔혹하게 살해했다."}
world_rules = [{"rule_id": "wr_001", "title": "계약 마법", "description": "마법은 계약 없이 발현될 수 없다", "violation_keywords": ["즉흥 마법", "계약 없이"]}]
characters = [{"character_id": "char_001", "name": "피터 파커", "core_values": ["폭력 회피"]}]
show("SCDS", run_scds(event, world_rules, characters))