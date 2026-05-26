"""Test standalone del parser de reservas de Syltek (sin dependencias externas)."""
import re
import sys
from datetime import date, datetime, time as dtime
from dataclasses import dataclass

# ---- Copiar solo la lógica del parser (sin imports del proyecto) ----

@dataclass
class FakeBooking:
    court_id: str
    court_name: str
    start_datetime: datetime
    end_datetime: datetime

def parse_slots(raw_html, day):
    bookings = []
    m_start = re.search(r'var\s+timetable\s*=\s*\{', raw_html)
    if not m_start:
        return bookings

    idx = m_start.start()
    brace = 0
    end_idx = idx
    in_str = False
    str_char = ""
    i = idx
    while i < len(raw_html):
        ch = raw_html[i]
        if in_str:
            if ch == str_char and raw_html[i - 1:i] != "\\":
                in_str = False
        else:
            if ch in ('"', "'"):
                in_str = True
                str_char = ch
            elif ch == "{":
                brace += 1
            elif ch == "}":
                brace -= 1
                if brace == 0:
                    end_idx = i
                    break
        i += 1

    timetable_js = raw_html[idx: end_idx + 1]

    resources = {}
    for m in re.finditer(r"""id\s*:\s*['"]?(\d+)['"]?\s*,\s*name\s*:\s*['"]([^'"]+)['"]""", timetable_js):
        cid = m.group(1)
        name = re.sub(r'\s*<[^>]+>\s*', ' ', m.group(2)).strip()
        resources[cid] = name or f"Pista {cid}"

    DATE_RE = re.compile(
        r'start\s*:\s*new\s+Date\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)', re.IGNORECASE)
    END_RE = re.compile(
        r'end\s*:\s*new\s+Date\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,'
        r'\s*(\d+)\s*,\s*(\d+)\s*,\s*\d+\s*\)', re.IGNORECASE)
    RES_RE = re.compile(r'idResource\s*:\s*\[([^\]]*)\]', re.IGNORECASE)

    seen = set()
    all_starts = list(DATE_RE.finditer(timetable_js))
    for idx_s, m_s in enumerate(all_starts):
        sh = int(m_s.group(4))
        sm = int(m_s.group(5))
        win_start = m_s.end()
        win_end = (all_starts[idx_s + 1].start()
                   if idx_s + 1 < len(all_starts)
                   else min(win_start + 1500, len(timetable_js)))
        window = timetable_js[win_start:win_end]
        m_end = END_RE.search(window)
        m_res = RES_RE.search(window)
        if not m_end or not m_res:
            wider = timetable_js[win_start: win_start + 2000]
            if not m_end: m_end = END_RE.search(wider)
            if not m_res: m_res = RES_RE.search(wider)
        if not m_end or not m_res:
            continue
        eh, em = int(m_end.group(1)), int(m_end.group(2))
        if not (0 <= sh <= 23 and 0 <= sm <= 59 and 0 <= eh <= 23 and 0 <= em <= 59):
            continue
        for cid in [c.strip() for c in m_res.group(1).split(',') if c.strip().isdigit()]:
            key = (cid, sh, sm)
            if key in seen:
                continue
            seen.add(key)
            bookings.append(FakeBooking(
                court_id=cid,
                court_name=resources.get(cid, f"Pista {cid}"),
                start_datetime=datetime.combine(day, dtime(sh, sm)),
                end_datetime=datetime.combine(day, dtime(eh, em)),
            ))
    return bookings


# ---- Test ----

test_html = """
<script>
var timetable = {
  startTime:1,
  resources:{
    1477:{id:'1477',name:'Padel 1 <br>  '},
    1478:{id:'1478',name:'Padel 2 <br>  '}
  },
  reservations:{
    111:{
      start: new Date(2026, 2, 27, 16, 0, 0),
      end: new Date(2026, 2, 27, 17, 30, 0),
      color:'FB7615',
      idResource:[1477]
    },
    222:{
      start:new Date(2026,2,27,20,30,0),end:new Date(2026,2,27,22,0,0),
      idResource:[1478]
    },
    333:{
      start : new Date( 2026, 2, 27, 19, 0, 0 ) ,
      end : new Date( 2026, 2, 27, 20, 30, 0 ) ,
      idResource : [ 1477 ]
    }
  }
};
</script>
"""

d = date(2026, 3, 27)
r1 = parse_slots(test_html, d)
r2 = parse_slots(test_html, d)
r3 = parse_slots(test_html, d)

print(f"Run 1: {len(r1)}  Run 2: {len(r2)}  Run 3: {len(r3)}")
for b in r1:
    print(f"  {b.court_name}: {b.start_datetime.strftime('%H:%M')} -> {b.end_datetime.strftime('%H:%M')}")

assert len(r1) == 3, f"FAIL: esperadas 3, obtenidas {len(r1)}"
assert len(r1) == len(r2) == len(r3), "FAIL: resultado no determinista"
print("\nTEST OK - parser es determinista y detecta los 3 formatos de fecha")
