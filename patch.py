import re

with open('backend/routers/analytics.py', 'r', encoding='utf-8') as f:
    content = f.read()

with open('scratch_resumen.py', 'r', encoding='utf-8') as f:
    replacement = f.read()

# Find the start of def resumen and the end
start_idx = content.find("def resumen(")
end_idx = content.find("# ── Ventas", start_idx)

if end_idx == -1:
    end_idx = content.find("# â”€â”€ Ventas", start_idx)

if start_idx != -1 and end_idx != -1:
    new_content = content[:start_idx] + replacement + "\n\n\n" + content[end_idx:]
    with open('backend/routers/analytics.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Replaced successfully.")
else:
    print("Pattern not found.", start_idx, end_idx)
