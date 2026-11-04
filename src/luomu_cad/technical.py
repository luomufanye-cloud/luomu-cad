"""Traceable technical learning cards and bounded training exercises.

These records preserve construction/system knowledge and scoped parameters.
An exercise pass is never a project design or construction approval.
"""
import copy
import hashlib
import json
import re
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from .storage import ROOT, atomic_json, now, workspace_lock

KINDS={"construction_detail","construction_method","professional_system","coordination"}


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}",value):
        raise ValueError("Invalid technical card id")
    return value


def validate_card(card):
    card=copy.deepcopy(card)
    identifier(card.get("id"))
    for key in ("title","discipline","topic"):
        if not isinstance(card.get(key),str) or not card[key].strip():raise ValueError(f"Missing {key}")
    if card.get("kind") not in KINDS or card.get("reviewed") is not True:
        raise ValueError("A reviewed technical category is required")
    if card.get("status") not in {"studied","exercise_checked","project_checked"}:
        raise ValueError("Use an evidence-based learning status")
    if card.get("auto_apply") is not False:
        raise ValueError("Technical learning cannot create global project defaults")
    scope=card.get("applicability",{})
    for key in ("jurisdiction","building_type","system_or_product","required_project_inputs","exclusions"):
        if not scope.get(key):raise ValueError(f"Missing applicability.{key}")
    sources=card.get("sources",[])
    if not isinstance(sources,list) or not sources:
        raise ValueError("A reviewed primary technical source is required")
    for source in sources:
        url=urlsplit(source.get("url",""))
        if url.scheme!="https" or not url.hostname or url.username or url.password or url.port not in (None,443):raise ValueError("Public HTTPS source URL required")
        try:address=ipaddress.ip_address(url.hostname)
        except ValueError:address=None
        if url.hostname.lower() in {"localhost","localhost.localdomain"} or (address is not None and not address.is_global):raise ValueError("Private source URL forbidden")
        for key in ("publisher","edition","locator","review_level","retrieved_at"):
            if not source.get(key):raise ValueError(f"Missing source {key}")
        if source.get("authority") not in {"government_standard","government_guidance","manufacturer_technical","verified_project_document"}:
            raise ValueError("Technical cards require an identified primary-source authority")
    for key in ("components","interfaces","procedure","checks","limits"):
        if not isinstance(card.get(key),list) or not card[key]:raise ValueError(f"Missing {key}")
    steps=[step.get("id") for step in card["procedure"]]
    if not all(isinstance(s,str) and s for s in steps) or len(set(steps))!=len(steps):raise ValueError("Distinct procedure step ids required")
    for rule in card.get("order_rules",[]):
        if not isinstance(rule,list) or len(rule)!=2 or rule[0] not in steps or rule[1] not in steps or rule[0]==rule[1]:raise ValueError("Invalid procedure order rule")
    for parameter in card.get("parameters",[]):
        for key in ("name","value","unit","source_url","source_locator","conditions"):
            if key not in parameter or parameter[key] in (None,"",[]):raise ValueError(f"Parameter missing {key}")
        if parameter["source_url"] not in {s["url"] for s in sources}:raise ValueError("Parameter source is not reviewed")
        if not parameter["conditions"]:raise ValueError("Parameter applicability conditions required")
        if parameter.get("adoption")!="reference_only":raise ValueError("Parameter must remain scoped reference knowledge")
    if card["status"]!="studied" and not card.get("assessment_evidence"):
        raise ValueError("An assessed status requires assessment evidence")
    if card["status"]=="project_checked" and not card.get("project_evidence"):
        raise ValueError("Project-checked status requires actual project evidence")
    return card


def check_sequence(card,proposed):
    card=validate_card(card)
    required=[s["id"] for s in card["procedure"]]
    if not isinstance(proposed,list) or not all(isinstance(s,str) for s in proposed):raise ValueError("Procedure must be a list of step ids")
    positions={s:i for i,s in enumerate(proposed)}
    issues=[]
    if len(positions)!=len(proposed):issues.append("duplicate steps")
    issues.extend("missing "+s for s in required if s not in positions)
    issues.extend("unknown "+s for s in proposed if s not in required)
    for before,after in card.get("order_rules",[]):
        if before in positions and after in positions and positions[before]>=positions[after]:issues.append(f"{before} must precede {after}")
    return {"ok":not issues,"issues":issues,"exercise_only":True,"engineering_approval":False}


def check_applicability(card,context):
    card=validate_card(card)
    def absent(value):
        if value is None:return True
        if isinstance(value,str):
            return value.strip().casefold() in {"","missing","unknown","unconfirmed","pending","tbd","待核实","待确认","未确认","缺失","待补充"}
        return isinstance(value,(list,dict,tuple)) and not value
    missing=[key for key in card["applicability"]["required_project_inputs"] if absent(context.get(key))]
    mismatches=[key for key,value in card.get("context_match",{}).items() if key in context and context[key]!=value]
    return {"ok":not missing and not mismatches,"missing_inputs":missing,"mismatches":mismatches,
            "auto_apply":False,"engineering_approval":False,"next":"project-specific design and source applicability review",
            "scope":"Required-input presence, explicit unknown markers and declared context matches only; no verification of input truth or engineering completeness"}


def check_connections(card,edges,context):
    """Graph exercise limited to the explicitly named portion of a schematic."""
    card=validate_card(card)
    rules=card.get("topology_exercise")
    if not rules or any(context.get(k)!=v for k,v in rules["context"].items()):
        raise ValueError("Topology exercise context mismatch; do not apply across systems or source bonding points")
    graph={}
    for edge in edges:
        if not isinstance(edge,list) or len(edge)!=2 or not all(isinstance(v,str) for v in edge):raise ValueError("Edges require two named training terminals")
        a,b=edge
        graph.setdefault(a,set()).add(b)
        graph.setdefault(b,set()).add(a)
    issues=[]
    for a,b in rules.get("must_remain_separate",[]):
        if a not in graph or b not in graph:issues.append(f"missing training terminal {a} or {b}");continue
        seen,pending=set(),[a]
        while pending:
            node=pending.pop()
            if node in seen:continue
            seen.add(node)
            pending.extend(graph.get(node,set())-seen)
        if b in seen:issues.append(f"unexpected connection between {a} and {b} in the stated exercise scope")
    return {"ok":not issues,"issues":issues,"exercise_only":True,"engineering_approval":False,
            "limits":"Named-terminal topology only; no voltage/current/protection/cable sizing validation"}


class TechnicalLibrary:
    def __init__(self,root=None):self.root=Path(root or ROOT/"references/technical")

    def get(self,card_id):
        path=self.root/(identifier(card_id)+".json")
        if not path.exists():raise ValueError("Unknown technical card")
        return validate_card(json.loads(path.read_text(encoding="utf-8")))

    def list(self):
        return [{k:c[k] for k in ("id","title","discipline","kind","status")} for c in
                (validate_card(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(self.root.glob('*.json')))]

    def record(self,card):
        card=validate_card(card)
        with workspace_lock(ROOT/"runtime/technical-library"):
            path=self.root/(card['id']+'.json')
            if path.exists():
                old=json.loads(path.read_text(encoding='utf-8'))
                if old==card:return {"ok":True,"unchanged":True,"card_id":card['id']}
                history=ROOT/'runtime/technical-history'/f"{card['id']}-{hashlib.sha256(path.read_bytes()).hexdigest()[:12]}.json"
                if not history.exists():atomic_json(history,old)
            atomic_json(path,card)
            return {"ok":True,"card_id":card['id'],"status":card['status'],"path":str(path),"auto_apply":False}
