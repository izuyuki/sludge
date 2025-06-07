import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import PyPDF2
import io
import requests
from bs4 import BeautifulSoup
import json

# 環境変数の読み込み
load_dotenv()

# Gemini APIの設定
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    st.error("GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()

genai.configure(api_key=api_key)

# モデルの設定
model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

# デジタル庁のデザインシステムに合わせたスタイル設定
st.set_page_config(
    page_title="スラスラ診断くん",
    page_icon="logo.png",
    layout="wide"
)

# カスタムCSS
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        background-color: #0066cc;
        color: white;
        border-radius: 4px;
        border: none;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #0052a3;
    }
    h1 {
        color: #333333;
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    h2 {
        color: #333333;
        font-size: 1.5rem;
        font-weight: bold;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .lead-text {
        font-size: 1.1rem;
        line-height: 1.6;
        color: #666666;
        margin-bottom: 2rem;
    }
    .step-title {
        color: #333333;
        font-weight: bold;
        font-size: 1.2rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .step-description {
        font-size: 0.9rem;
        line-height: 1.6;
        color: #666666;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        st.error(f"PDFの読み込みに失敗しました: {str(e)}")
        return None

def search_related_info(text):
    # ここでGeminiを使用して関連情報を検索
    prompt = f"""
    以下の行政文書の内容に関連する情報を検索し、重要な情報を抽出してください：
    {text}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"関連情報の検索に失敗しました: {str(e)}")
        return None

def analyze_persona(text, related_info):
    prompt = f"""
    以下の行政文書と関連情報を分析し、想定されるターゲットを特定してください：
    
    文書内容：
    {text}
    
    関連情報：
    {related_info}
    
    以下の4項目について、各100字程度で簡潔にまとめ、必ずMarkdown表（| 項目 | 内容 |）で出力してください。
    | 項目 | 内容 |
    |------|------|
    | 1. 主要なターゲットの特徴 |  |
    | 2. 想定される年齢層 |  |
    | 3. 想定される生活状況 |  |
    | 4. 想定される課題やニーズ |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"ターゲット分析に失敗しました: {str(e)}")
        return None

def analyze_target_action(text, persona):
    prompt = f"""
    以下の行政文書とターゲット情報を分析し、促したい行動を特定してください：
    
    文書内容：
    {text}
    
    ターゲット情報：
    {persona}
    
    主要な目標行動のみを100字程度で出力してください。
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"目標行動の分析に失敗しました: {str(e)}")
        return None

def create_action_process_map(text, target_action):
    prompt = f"""
    以下の情報を基に、行動プロセスマップを作成してください：
    
    文書内容：
    {text}
    
    目標行動：
    {target_action}
    
    以下の形式でMarkdown表を作成してください。
    | ステップ | 必要な情報 | 想定される摩擦 | この文書との接点 |
    |---------|------------|----------------|------------------|
    
    接点が強い部分には「◎」、中程度には「○」、弱い部分には「△」の印を「この文書との接点」列に記載してください。
    各セルは簡潔に箇条書きで記載してください。
    <br>などのHTMLタグや特殊記号は使わず、Markdown表として出力してください。
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"行動プロセスマップの作成に失敗しました: {str(e)}")
        return None

def analyze_east_framework(text, process_map):
    prompt = f"""
    スラッジの観点から、以下の情報を分析してください。
    ※ここでは改善案や提案は出さず、分析のみを行ってください。
    
    文書内容：
    {text}
    
    行動プロセスマップ：
    {process_map}
    
    以下の3観点について、必ずMarkdown表（| 項目 | チェック内容 | 分析結果 |）で出力してください。
    各「分析結果」は必ず箇条書きでまとめてください。
    <br>などのHTMLタグや特殊記号は使わず、純粋なMarkdown表で出力してください。
    | 項目 | チェック内容 | 分析結果 |
    |------|------------|----------|
    | 1. 情報の簡潔性 | 真に必要な情報に限定されているか。難解な言葉や冗長な文章が使われてないか。 |  |
    | 2. 情報の構造性 | 情報は項目ごとに整理され、視覚的にわかりやすく、優先度や時系列にそって配置されているか。情報の重複はないか。 |  |
    | 3. 動作指示の明確性 | いつ、どこで、誰が、どのように行動すべきか明確に記載されているか |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"スラッジ分析に失敗しました: {str(e)}")
        return None

def generate_improvement_suggestions(text, east_analysis):
    prompt = f"""
    以下の分析結果を基に、文書の改善案を提案してください：
    
    原文書：
    {text}
    
    スラッジ分析：
    {east_analysis}
    
    以下の観点を踏まえ、Easy（簡単さ）に特化した重要な改善ポイント5つを厳選し、①～⑤の番号を振って、必ずMarkdown表（| 改善ポイント | 具体的な改善案 |）で出力してください。
    各「具体的な改善案」は必ず箇条書きでまとめてください。
    <br>などのHTMLタグや特殊記号は使わず、純粋なMarkdown表で出力してください。
    | 改善ポイント | 具体的な改善案 |
    |------------|----------------|
    | ①  |  |
    | ②  |  |
    | ③  |  |
    | ④  |  |
    | ⑤  |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"改善案の生成に失敗しました: {str(e)}")
        return None

def generate_process_optimization_ideas(text, east_analysis, process_map):
    prompt = f"""
    以下の分析結果と行動プロセスマップを基に、プロセス全体を最適化するための、このファイル以外の改善アイデアを5つ提案してください。
    ※必ずアップロードしたファイル自体の改善以外のことを提案し、上段の改善案と重複しないようにしてください。
    ※全体の行動プロセスマップを踏まえた提案にしてください。
    
    原文書：
    {text}
    
    スラッジ分析：
    {east_analysis}
    
    行動プロセスマップ：
    {process_map}
    
    必ずMarkdown表（| 改善アイデア | 内容 |）で5つ出力してください。
    <br>などのHTMLタグや特殊記号は使わず、純粋なMarkdown表で出力してください。
    | 改善アイデア | 内容 |
    |------------|------|
    | ①  |  |
    | ②  |  |
    | ③  |  |
    | ④  |  |
    | ⑤  |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"プロセス全体の最適化アイデアの生成に失敗しました: {str(e)}")
        return None

# Streamlit UI
# ロゴの表示
st.image("logo.png", width=100)

st.title("スラスラ診断くん")
st.markdown('行動科学の知見と生成AIにより、行政文書やチラシに潜む<span style="font-weight: bold;">"スラッジ"</span>（複雑さ、煩雑さ、難解さといった行動を妨げる要因）を特定し、<span style="font-weight: bold;">"スラスラ"</span>読んで行動できるよう改善するための初期診断ツールです。', unsafe_allow_html=True)

st.markdown("""
| あなたの行動ステップ | このツールができること |
|---------|-------------------|
| **Step1** チラシなどのPDF文書（１ファイル）をアップロードしてください。 | 文書のターゲット、促したい目標行動、そこに至るプロセスを可視化し、スラッジを特定します。 |
| **Step2** 診断結果を踏まえて、チラシなどを実際に改善してください。 | すぐに取り組める"重要な改善ポイント５選"を提示します（改善文書の自動生成機能は、現在準備中です）。 |
| **Step3** 文書以外の改善ができないか、プロセス全体を見直してください。 | アップロードした文書以外の改善アイデアも提示します。 |
""", unsafe_allow_html=True)

# アップロードエリアの幅を調整
with st.container():
    col1, col2 = st.columns([2, 3])
    with col1:
        uploaded_file = st.file_uploader("PDFファイルをここにアップロードしてください", type=['pdf'])

if uploaded_file is not None:
    with st.spinner("分析中..."):
        # PDFからテキストを抽出
        text = extract_text_from_pdf(uploaded_file)
        if text:
            # 関連情報の検索
            related_info = search_related_info(text)
            
            # ターゲット分析
            persona = analyze_persona(text, related_info)
            st.subheader("想定されるターゲット")
            st.markdown(persona)
            
            # 目標行動の分析
            target_action = analyze_target_action(text, persona)
            st.subheader("目標行動")
            st.markdown(target_action)
            
            # 行動プロセスマップの作成
            process_map = create_action_process_map(text, target_action)
            st.subheader("行動プロセスマップ")
            st.markdown(process_map)
            
            # スラッジ分析
            east_analysis = analyze_east_framework(text, process_map)
            st.subheader("スラッジ分析")
            
            # スラッジ分析の実行
            analysis_result = analyze_sludge(text)
            
            # 結果の表示
            st.markdown("### スラッジ分析結果")
            
            # 良い点の表示
            st.markdown("#### 良い点")
            good_points = []
            if "明確な目的" in analysis_result and analysis_result["明確な目的"]:
                good_points.append("目的が明確に示されています")
            if "具体的な行動" in analysis_result and analysis_result["具体的な行動"]:
                good_points.append("具体的な行動が示されています")
            if "期限の明示" in analysis_result and analysis_result["期限の明示"]:
                good_points.append("期限が明確に示されています")
            if "連絡先情報" in analysis_result and analysis_result["連絡先情報"]:
                good_points.append("連絡先情報が適切に記載されています")
            
            if good_points:
                for point in good_points:
                    st.markdown(f"✅ {point}")
            else:
                st.markdown("⚠️ 特に良い点は見つかりませんでした")
            
            # 改善点の表示
            st.markdown("#### 改善点")
            if not analysis_result["明確な目的"]:
                st.markdown("❌ 目的が不明確です。何をすべきか、なぜそれが必要なのかを明確に示してください。")
            if not analysis_result["具体的な行動"]:
                st.markdown("❌ 具体的な行動が示されていません。何を、いつ、どのように行うべきかを具体的に説明してください。")
            if not analysis_result["期限の明示"]:
                st.markdown("❌ 期限が明示されていません。いつまでに行動すべきかを明確に示してください。")
            if not analysis_result["連絡先情報"]:
                st.markdown("❌ 連絡先情報が不足しています。問い合わせ先や担当者を明記してください。")
            
            # 改善提案の表示
            st.markdown("### 改善提案")
            st.markdown(analysis_result["改善提案"].replace("<br>", "\n\n"), unsafe_allow_html=True)

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
