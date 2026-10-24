import re, base64, pathlib
root = pathlib.Path(__file__).parent
s = (root / "web/index.html").read_text(encoding="utf-8")
for w in ("400", "600"):
    b = base64.b64encode((root / f"web/fonts/fraunces-latin-{w}-normal.woff2").read_bytes()).decode()
    s = s.replace(f"url(fonts/fraunces-latin-{w}-normal.woff2)", f"url(data:font/woff2;base64,{b})")
m = re.search(r'@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\) \{(.*?)\}\s*\}', s, re.S)
s = s.replace(m.group(0), m.group(0) + '\n:root[data-theme="dark"] {' + m.group(1) + '}')
s = s.replace("html, body { margin: 0; height: 100%; }", "html, body { margin: 0; min-height: 100%; }")
s = s.replace("<title>数独</title>", "<title>数独 100 关</title>")
(root / "preview_full.html").write_text(s, encoding="utf-8")          # 本地双击打开用
body = re.sub(r'<!doctype html>\s*<html[^>]*>\s*<head>\s*', '', s)
body = re.sub(r'<meta [^>]*>\s*', '', body)
body = body.replace("</head>\n<body>\n", "").replace("</body>\n</html>\n", "")
(root / "preview_artifact.html").write_text(body, encoding="utf-8")   # 发布用
print("ok")
