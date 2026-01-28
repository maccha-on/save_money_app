import os

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from openai import OpenAI
import pandas as pd
import psycopg
from pydantic import BaseModel


# =========================
# FAST APIの起動設定
# =========================
app = FastAPI()

# =========================
# .envの設定
# =========================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

# ================================================================
# 画面（index.html）を返す設定
# 起動したFastAPIが、index.htmlを読み込んでブラウザに表示させています。
# ================================================================
@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/style.css")
def get_style():
	return FileResponse("style.css")

# =============================
# データ登録(add)のJSON形式を規定
# =============================
class AddRequest(BaseModel):
    user: str
    item: str
    price: int
    entryDate: str

# =========================
# supabaseに入力内容を保存
# =========================

def save_to_db(req: AddRequest):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            # idは指定しない（DBに任せる）
            cur.execute(
                "INSERT INTO public.c5wallet_rireki (username, item, price, date) VALUES (%s, %s, %s, %s) returning id;",
                (req.user, req.item, req.price, req.entryDate)
            )
            new_id = cur.fetchone()[0]
            conn.commit()

# =========================
# supabaseから履歴を取得＆pandas DataFrameとして読み込み
# =========================

# userの全データと合計金額を取得する
def get_from_db(user: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM c5wallet_rireki WHERE username = %s',(user,))
            df = pd.DataFrame(cur.fetchall(), columns=[col.name for col in cur.description])
            cur.execute('SELECT SUM(price) FROM c5wallet_rireki WHERE username = %s',(user,))
            total_money_from_db = cur.fetchone()[0] or 0
    return df, total_money_from_db

# userの今月のデータと合計金額を取得する
def get_this_month_data_from_db(user: str):
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT price,date,item FROM c5wallet_rireki
                WHERE username = %s AND (date >= date_trunc('month', CURRENT_DATE) AND date < date_trunc('month', CURRENT_DATE) + interval '1 month');
            """,
                (user,)
            )
            df = pd.DataFrame(cur.fetchall(), columns=[col.name for col in cur.description])
            cur.execute("""
                SELECT SUM(price) FROM c5wallet_rireki
                WHERE username = %s AND (date >= date_trunc('month', CURRENT_DATE) AND date < date_trunc('month', CURRENT_DATE) + interval '1 month');
                """,
                (user,)
            )
            total_money_from_db = cur.fetchone()[0] or 0
    return df, total_money_from_db

# =========================
# 追加（保存）API：POST /add
# =========================

@app.post("/add")
def add_record(req: AddRequest):
    print(f"ADDサービスが受け取ったreqデータ:\n {req}") # データ確認用

    # supabaseに保存する
    save_to_db(req)

    # ブラウザに返すメッセージ（JSON）
    return {"message": f"{req.user} さんの{req.item}を保存しました"}

# =====================
# 履歴API：GET /history
# =====================
@app.get("/history")
def analyze_user(user: str = Query(..., description="ユーザー名")):
    # データ取得
    df, total_money_from_db = get_from_db(user)
    # 空なら
    if df.empty:
        return {
            "message": "データを取得しました",
            "total_money": 0,
            "history": ["データがありませんでした"],
        }
    # データがあれば返す
    history = []
    for index,row in df.iterrows():
        history.append(f"{row['date'].strftime('%Y-%m-%d')} : {row['item']} : {row['price']}円\n")
    return {
        "message": "データを取得しました",
        "total_money": total_money_from_db,
        "history": history,
    }

# =====================
# 分析API：GET /analyze
# =====================
@app.get("/analyze")
def analyze_user(user: str = Query(..., description="ユーザー名"),
                coach: str = Query(..., description="コーチの種類"),
                budget: int = Query(..., description="予算")):
    # v3で追加
    if user == '':
        return {"message": "ユーザー名を入れてください"}
    if budget == 0:
        return {"message": "予算を入力してください"}

    # Supabaseから合計金額を取得
    df, total_money = get_this_month_data_from_db(user)

    if df.empty:
        return {
            "message": f"{user}さんのデータはありません",
        }

    # コーチによってプロンプトを変更
    if coach == "oni":
        prompt = """
            あなたは20年以上の経験を持つ優秀なファイナンシャルプランナーです。
            ユーザーの目標を達成するために必要な厳しい指導を具体的に提示してください。
            * 分析内容
            - 目標支出金額と現在の支出額を比較し、目標とどれだけ差があるか確認する
            - 目標からオーバーしてしまった場合は、かなり辛口で指導する
            - 目標から遠い場合も厳しく指導する

            * トーン
            - 全体的に厳しい口調でユーザーに接する
            - 忖度なしで意見を述べる
        """
    else:
        prompt = """
            あなたは20年以上の経験を持つ優秀なファイナンシャルプランナーです。
            ユーザーの目標を達成するためにポジティブに甘やかす指導を具体的に提示してください。
            * 分析内容
            - 目標支出金額と現在の支出額を比較し、目標とどれだけ差があっても攻めたりはしない
            - 目標から適切な支出ペースの場合は、かなり甘口で褒める
            - 目標からオーバーしてしまった場合は、かなり甘口で励ます
            - 目標から遠い場合も優しく指導する
            - ただし、生活の質は落とさないように、我慢や制限を強制しないでください

            * トーン
            - 全体的に甘い口調でユーザーに接する
            - 忖度なしで甘い意見を述べる
        """

    # AIに指示
    response = client.responses.create(
        model = "gpt-4.1-mini",
        instructions=prompt,
        input=f"""
            目標支出額{budget}に対して、今月{total_money}円使用しています。
            目標支出額内に抑えられるための具体例を3つ提示してください。
            参考：支出履歴
            {df}
        """
    )

    return {"message": f"{user} の分析結果:\n {total_money}\nAIの回答{response.output_text}"}
