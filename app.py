import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from dotenv import load_dotenv
import os

# 環境変数の読み込み
load_dotenv()

# Gemini APIの設定
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    st.error("GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()

genai.configure(api_key=api_key)

# 利用可能なモデルを確認
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            pass  # 何も表示しない
except Exception as e:
    st.error(f"モデル一覧の取得に失敗しました: {str(e)}")

# モデルの設定
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

# チェックリストの定義
CHECKLIST = """
ナビゲーションの明確さ: ユーザーが目的の情報に迅速にアクセスできるよう、直感的なナビゲーションが設計されていますか？
情報の整理: 重要な情報が目立つように配置され、ユーザーが容易に見つけられるようになっていますか？
視覚的要素の一貫性: アイコンや色使いが一貫しており、情報の重要度やカテゴリーが視覚的に区別されていますか？
テキストの構造: 長文が適切に分割され、見出しや箇条書きを用いて読みやすくなっていますか？
空白の活用: 適切な余白が設けられ、情報が詰め込みすぎず、視認性が確保されていますか？
平易な言葉の使用: 専門用語や法律用語を避け、誰にでも理解しやすい言葉で書かれていますか？
一貫した用語の使用: 同じ概念や項目について、異なる用語が使われていませんか？
用語の定義: 必要に応じて、難解な用語や略語に対する説明や定義が提供されていますか？
"""

def get_webpage_content(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")
        return None

# --- Geminiプロンプト ---
def analyze_webpage(content, url):
    prompt = f"""
    あなたは行動科学の専門家です。
    以下の手順で作業してください：
    1. ユーザーが入力したURLのウェブサイト内容を正確に理解してください。
    2. わかりづらい点を大きく修正するのではなく、行動科学の観点から利用者の行動を後押しするような微修正のみを行ってください（例：行動を促す表現への言い換え、選択肢の提示順序の工夫、注目を集めるための小さな強調など）。内容や趣旨は必ず維持してください。
    3. 修正したものをテキストデータで出力してください（HTMLではなく、見出し・本文・箇条書き・表などを適切に使い、すぐにコピペして使える日本語で）。
    4. 修正ポイントを表形式で1回だけまとめてください。
    
    ※内容や趣旨は必ず維持し、情報の追加や削除、想像による追記は行わないでください。
    
    出力例：
    【修正版テキスト】
    ...（ここに修正後のテキスト）...
    
    【修正ポイント（表形式）】
    | 修正箇所 | 微修正内容 |
    |---|---|
    | 見出し | 例：行動を促す表現に微修正 |
    ...
    
    # 対象ページURL
    {url}
    
    # ページ内容
    {content}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Gemini APIでエラーが発生しました: {str(e)}")
        st.error("APIキーが正しく設定されているか確認してください。")
        return None

# Streamlit UI
st.image("water_logo.png", width=120)  # 幅はお好みで調整
st.title("スラッジ・ファインダー")
st.write("URLを入力して、ウェブページの改善点を確認しましょう。")

url = st.text_input("ウェブページのURLを入力してください：")

if st.button("分析開始"):
    if url:
        with st.spinner("ウェブページを分析中..."):
            content = get_webpage_content(url)
            if content:
                analysis = analyze_webpage(content, url)
                if analysis:
                    import re
                    st.subheader("分析結果")
                    # 修正版テキスト
                    page_plan_match = re.search(r'【修正版テキスト】([\s\S]+?)(?=\n\s*【|$)', analysis)
                    if page_plan_match:
                        st.subheader("修正版テキスト")
                        st.write(page_plan_match.group(1).strip())
                    # 修正ポイント（表形式）は1回だけ表示
                    table_match = re.search(r'【修正ポイント（表形式）】([\s\S]+?)(?=\n\s*【|$)', analysis)
                    if table_match:
                        st.subheader("修正ポイント（表形式）")
                        st.markdown(table_match.group(1))
    else:
        st.warning("URLを入力してください。")

# フッターに「氷解社が作成」と記載
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">このアプリは氷解社が作成しています</div>', unsafe_allow_html=True) 
