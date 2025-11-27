from pathlib import Path
text=Path('app/core/logging.py').read_text(encoding='utf-8')
text=text.replace("from datetime import datetime\nfrom typing import Optional","from datetime import datetime\nfrom typing import Optional\nfrom zoneinfo import ZoneInfo")
text=text.replace("return f\"{dt.hour:02d}시 {dt.minute:02d}분 {dt.second:02d}초\"","return f\"{dt.hour:02d}시 {dt.minute:02d}분 {dt.second:02d}초\"\n\n\n")
Path('app/core/logging.py').write_text(text,encoding='utf-8')
