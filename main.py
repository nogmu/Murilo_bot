import requests, json, time, threading, datetime, os

TOKEN = os.environ.get("BOT_TOKEN", "8572315166:AAGPC3ykHJzGCE4YygC5rbYkesIoZqGj5bw")
BASE  = f"https://api.telegram.org/bot{TOKEN}"
DATA_FILE = "/tmp/murilo_bot_data.json"

TASKS_TEMPLATE = {
    "ingles1":   {"name": "🇬🇧 Inglês intervalo 1",  "points": 25, "done": False},
    "ingles2":   {"name": "🎧 Inglês intervalo 2",   "points": 20, "done": False},
    "almoco":    {"name": "🥗 Almoço de verdade",    "points": 20, "done": False},
    "lanche":    {"name": "🍎 Lanche saudável",      "points": 15, "done": False},
    "faculdade": {"name": "📚 Tarefa da faculdade",  "points": 35, "done": False},
    "exercicio": {"name": "🏃 Exercício físico",     "points": 40, "done": False},
    "descanso":  {"name": "😴 Respeitar o descanso", "points": 20, "done": False},
}

SCHEDULE = [
    (7,  30, "manha",  ["ingles1","ingles2","almoco","lanche","faculdade","exercicio","descanso"]),
    (12,  0, "almoco", ["almoco","ingles1"]),
    (18,  0, "tarde",  ["ingles2","faculdade"]),
    (21,  0, "noite",  ["exercicio","faculdade","descanso"]),
    (23,  0, "resumo", []),
]

MSGS = {
    "manha":  "🌅 *Bom dia, Murilo!* Hoje você pode marcar até *175 pts*.\n\n🏃 Exercício — *+40*\n📚 Faculdade — *+35*\n🇬🇧 Inglês 1 (12h) — *+25*\n🎧 Inglês 2 (18h) — *+20*\n🥗 Almoço — *+20*\n😴 Descanso — *+20*\n🍎 Lanche — *+15*\n\n_Progresso pequeno, mas constante._ 💪",
    "almoco": "⏰ *12h — Intervalo 1!*\n\n🥗 Almoço de verdade\n🇬🇧 Inglês por 20 min\n\nMarca abaixo 👇",
    "tarde":  "⏰ *18h — Intervalo 2!*\n\n🎧 Inglês sem legenda\n📚 Tarefa da faculdade depois\n\nMarca abaixo 👇",
    "noite":  "🌙 *21h — Reta final!*\n\n🏃 Exercício\n📚 Faculdade\n😴 Descanso\n\nMarca o que já fez 👇",
}

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: return json.load(f)
        except: pass
    return {"chat_id": None, "date": "", "tasks": {}, "sent_schedules": []}

def save_data(d):
    with open(DATA_FILE, "w") as f: json.dump(d, f, ensure_ascii=False)

def reset_day(data):
    today = datetime.date.today().isoformat()
    if data.get("date") != today:
        data.update({"date": today, "tasks": {k: dict(v) for k,v in TASKS_TEMPLATE.items()}, "sent_schedules": []})
        save_data(data)
    return data

def api(method, **kw):
    try: return requests.post(f"{BASE}/{method}", json=kw, timeout=15).json()
    except: return {}

def send(cid, text, kb=None):
    p = {"chat_id": cid, "text": text, "parse_mode": "Markdown"}
    if kb: p["reply_markup"] = kb
    return api("sendMessage", **p)

def edit_msg(cid, mid, text, kb=None):
    p = {"chat_id": cid, "message_id": mid, "text": text, "parse_mode": "Markdown"}
    if kb: p["reply_markup"] = kb
    api("editMessageText", **p)

def build_kb(keys, tasks):
    btns = [[{"text": ("✅ " if tasks.get(k,{}).get("done") else "⬜ ") + tasks.get(k, TASKS_TEMPLATE[k])["name"] + f" (+{tasks.get(k, TASKS_TEMPLATE[k])['points']} pts)", "callback_data": f"done:{k}"}] for k in keys]
    btns.append([{"text": "📊 Ver pontuação", "callback_data": "status"}])
    return {"inline_keyboard": btns}

def pts(tasks): return sum(t["points"] for t in tasks.values() if t.get("done"))

def status_text(tasks):
    p = pts(tasks)
    lines = [f"*📊 {p}/175 pts*\n"] + [("✅ " if t.get("done") else "⬜ ") + f"{t['name']} (+{t['points']})" for t in tasks.values()]
    bar = "█"*(p//175*10) + "░"*(10-p//175*10)
    lines.append(f"\n[{'█'*(int(p/175*10))}{'░'*(10-int(p/175*10))}] {int(p/175*100)}%")
    return "\n".join(lines)

def handle(upd, data):
    if "message" in upd:
        msg = upd["message"]; cid = msg["chat"]["id"]; text = msg.get("text","")
        if data["chat_id"] is None:
            data["chat_id"] = cid; save_data(data)
            send(cid, "👋 *Bot ativado!*\n/status — pontuação\n/tarefas — missões\n/reset — reiniciar dia"); return
        if text in ("/start","/ajuda"): send(cid, "/status /tarefas /reset /ajuda")
        elif text == "/status": send(cid, status_text(data["tasks"]))
        elif text == "/tarefas": send(cid, "📋 *Missões de hoje:*", kb=build_kb(list(TASKS_TEMPLATE), data["tasks"]))
        elif text == "/reset": data["date"]=""; reset_day(data); send(cid, "🔄 Reiniciado!")
        else: send(cid, "Use /ajuda para ver os comandos.")
    elif "callback_query" in upd:
        cb = upd["callback_query"]; cid = cb["message"]["chat"]["id"]; mid = cb["message"]["message_id"]
        if cb["data"].startswith("done:"):
            k = cb["data"].split(":",1)[1]
            if k in data["tasks"]:
                t = data["tasks"][k]; t["done"] = not t["done"]; save_data(data)
                api("answerCallbackQuery", callback_query_id=cb["id"], text=f"+{t['points']} pts! 🎉" if t["done"] else "Desmarcado")
                keys = [b["callback_data"].split(":",1)[1] for row in cb["message"].get("reply_markup",{}).get("inline_keyboard",[]) for b in row if b.get("callback_data","").startswith("done:")]
                edit_msg(cid, mid, cb["message"].get("text",""), kb=build_kb(keys or list(TASKS_TEMPLATE), data["tasks"]))
                if all(t.get("done") for t in data["tasks"].values()): send(cid, "🏆 *175/175 pts! Incrível!* 🌙")
        elif cb["data"] == "status":
            api("answerCallbackQuery", callback_query_id=cb["id"])
            send(cid, status_text(data["tasks"]))

def scheduler():
    while True:
        try:
            now = datetime.datetime.now(); today = now.strftime("%Y-%m-%d"); h,m = now.hour, now.minute
            data = load_data(); data = reset_day(data); cid = data.get("chat_id")
            if cid:
                sent = data.get("sent_schedules",[])
                for sh,sm,slug,keys in SCHEDULE:
                    key = f"{today}-{sh}:{sm:02d}"
                    if h==sh and m==sm and key not in sent:
                        if slug=="resumo":
                            p = pts(data["tasks"])
                            send(cid, f"🌙 *Resumo do dia!*\n\n{status_text(data['tasks'])}\n\n{'🏆 Arrasou!' if p>=140 else '💪 Amanhã vai além!'}")
                        else:
                            send(cid, MSGS[slug], kb=build_kb(keys, data["tasks"]))
                        sent.append(key); data["sent_schedules"]=sent; save_data(data)
        except Exception as e: print(f"Scheduler: {e}")
        time.sleep(30)

threading.Thread(target=scheduler, daemon=True).start()
offset = 0
print("Bot rodando!")
while True:
    try:
        for upd in requests.get(f"{BASE}/getUpdates", params={"offset":offset,"timeout":30}, timeout=35).json().get("result",[]):
            offset = upd["update_id"]+1
            data = reset_day(load_data())
            handle(upd, data)
    except Exception as e: print(f"Polling: {e}"); time.sleep(5)
