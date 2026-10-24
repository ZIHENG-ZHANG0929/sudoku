import json, pathlib
root = pathlib.Path(__file__).parent
P = json.load(open(root / "gen/puzzles.json"))
data = json.dumps([{"p": x["p"], "s": x["s"]} for x in P], separators=(",", ":"))
src = (root / "web/src.html").read_text(encoding="utf-8")
engine = (root / "web/engine.js").read_text(encoding="utf-8")
lessons = (root / "gen/lessons.json").read_text(encoding="utf-8")
P6 = (root / "gen/puzzles6.json").read_text(encoding="utf-8")
out = src.replace("/*PUZZLES*/", data).replace("/*PUZZLES6*/", P6).replace("/*ENGINE*/", engine).replace("/*LESSONS*/", lessons)
(root / "web/index.html").write_text(out, encoding="utf-8")
print("ok")
import shutil
www = root / "android/app/src/main/assets/www"
shutil.rmtree(www, ignore_errors=True)
(www / "fonts").mkdir(parents=True)
shutil.copy(root / "web/index.html", www / "index.html")
for f in (root / "web/fonts").iterdir():
    shutil.copy(f, www / "fonts" / f.name)
print("assets copied")
