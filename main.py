from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime, timedelta
import csv

# v3で追加
from openai import OpenAI
from dotenv import load_dotenv
import os

# =========================
# FAST APIの起動設定
# =========================
CSV_PATH = "data.csv"
app = FastAPI()

# v3で追加
# =========================
# ChatGPT API_KEYの設定
# =========================

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================================================================
# 画面（index.html）を返す設定
# 起動したFastAPIが、index.htmlを読み込んでブラウザに表示させています。
# ================================================================
@app.get("/")
def root():
    return FileResponse("index.html")

# =============================
# データ登録(add)のJSON形式を規定
# =============================
class AddRequest(BaseModel):
    user: str
    item: str
    price: int

# =========================
# 追加（保存）API：POST /add
# =========================
# ブラウザから送られたデータを、CSVに1行追加します。
@app.post("/add")
def add_record(req: AddRequest):
    print(f"ADDサービスが受け取ったreqデータ:\n {req}") # データ確認用

    # 
    # 【タスク3】データの書き込み
    #   CSVファイルにデータを追記してください。
    #     ヒント1: requestの各値は req.user, req.item, req.price で取れます。 
    #     ヒント2: 今日の日付は、datetime.now().date() で取得できます。
    #     ヒント3: CSVファイルは、次のようにすると追記モードで開けます。
    #       with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
    #

    # 今日の日付を取得
    timestamp = datetime.now().strftime('%Y-%m-%d')

    # CSVに保存する
    with open(CSV_PATH, "a", newline="", encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([req.user, timestamp, req.item, req.price])

    # ブラウザに返すメッセージ（JSON）
    return {"message": f"{req.user} さんの{req.item}を保存しました"}


# =====================
# 分析API：GET /analyze
# =====================
@app.get("/analyze")
def analyze_user( user: str = Query(..., description="ユーザー名")):
    # MEMO：30日間のデータを返すための日付を取得
    # before_7day = datetime.now() - timedelta(days=30)

		# v3で追加
    if user == '':
        return {"message": "ユーザー名を入れてください"}

    # 合計金額
    total_money = 0

    # ====== 該当ユーザーのデータをCSVから抽出 ======
    data_txt = "user,timestamp,item,price\n" # データを入れる
    with open(CSV_PATH, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)                # CSVを辞書形式で読む
        for row in reader:
            print(row)                       # CSVを1行ずつ読む
            if row["user"] != user: # 指定ユーザー以外はスキップ
                continue
            # MEMO:一旦コメントアウト（30日前までのデータは省く）
            # date = datetime.strptime(row["timestamp"], "%Y-%m-%d")
            # if date <= before_7day:
            #     continue
            # data_txt に行の内容を付け足し
            data_txt += f'{row["user"]},{row["timestamp"]},{row["item"]},{row["price"]}\n'
            # 合計金額を足す
            total_money = total_money + int(row["price"])
    # 
    # 【タスク4】データの計算
    #     現在は、該当ユーザーのデータを全部引っ張ってきています。
    #     1週間や1か月など、集計する期間のデータを抽出してください。
    #     * 合計額なども計算するといいかもですね。
    # 
    print('data_txtの内容', data_txt) # 確認・デバッグ用

    # 
    # 【タスク5】（最難関） 生成AI APIの利用
    #   data_txtの内容などを利用しながら、OPENAI(Chat GPT) APIに送り、分析結果を取得してください。
    #   プロンプトも色々と工夫してみてください。
    # 

		# v3で追加
    monthly_budget_goal = 20000 # 仮の目標額
    response = client.responses.create(
        model = "gpt-4.1-mini",
        instructions="""
        あなたは20年以上の経験を持つ優秀なファイナンシャルプランナーです。
        ユーザーの目標を達成するために必要な厳しい指導を具体的に提示してください。
        * 分析内容
        - 目標支出金額と現在の支出額を比較し、目標とどれだけ差があるか確認する
        - 目標からオーバーしてしまった場合は、かなり辛口で指導する
        - 目標から遠い場合も厳しく指導する

        * トーン
        - 全体的に厳しい口調でユーザーに接する
        - 忖度なしで意見を述べる
        """,
        input=f"""
        目標支出額{monthly_budget_goal}に対して、今月{total_money}円使用しています。
        目標支出額内に抑えられるための具体例を3つ提示してください。
        """
    )

    result = data_txt  # 今はCSVデータをそのまま返しているだけ

    return {"message": f"{user} の分析結果:\n {total_money}"}
