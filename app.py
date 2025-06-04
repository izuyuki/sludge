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
    以下の行政文書と関連情報を分析し、想定されるペルソナを特定してください：
    
    文書内容：
    {text}
    
    関連情報：
    {related_info}
    
    以下の4項目について、各100字程度で簡潔にまとめ、必ずMarkdown表（| 項目 | 内容 |）で出力してください。
    | 項目 | 内容 |
    |------|------|
    | 1. 主要なペルソナの特徴 |  |
    | 2. 想定される年齢層 |  |
    | 3. 想定される生活状況 |  |
    | 4. 想定される課題やニーズ |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"ペルソナ分析に失敗しました: {str(e)}")
        return None

def analyze_target_action(text, persona):
    prompt = f"""
    以下の行政文書とペルソナ情報を分析し、促したい行動を特定してください：
    
    文書内容：
    {text}
    
    ペルソナ情報：
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
    行動科学の観点から、特にEasy（簡単さ）に特化して、以下の情報を分析してください。
    ※ここでは改善案や提案は出さず、分析のみを行ってください。
    
    文書内容：
    {text}
    
    行動プロセスマップ：
    {process_map}
    
    以下の3観点について、必ずMarkdown表（| 観点 | 分析内容 |）で出力してください。
    | 観点 | 分析内容 |
    |------|----------|
    | 1. 情報の簡潔さ |  |
    | 2. 情報の整理（配置、時系列、視覚的整理、項目、重複有無） |  |
    | 3. 動作指示の明確性（いつ、どこで、誰が、どのように） |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"行動科学分析に失敗しました: {str(e)}")
        return None

def generate_improvement_suggestions(text, east_analysis):
    prompt = f"""
    以下の分析結果を基に、文書の改善案を提案してください：
    
    原文書：
    {text}
    
    行動科学分析：
    {east_analysis}
    
    以下の観点を踏まえ、Easy（簡単さ）に特化した重要な改善ポイント5つを厳選し、①～⑤の番号を振って、必ずMarkdown表（| 番号 | 改善ポイントと具体的な改善案 |）で出力してください。
    | 番号 | 改善ポイントと具体的な改善案 |
    |------|-----------------------------|
    | ① |  |
    | ② |  |
    | ③ |  |
    | ④ |  |
    | ⑤ |  |
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"改善案の生成に失敗しました: {str(e)}")
        return None

def generate_process_optimization_ideas(text, east_analysis):
    prompt = f"""
    以下の分析結果を基に、プロセス全体を最適化するための、このファイル以外の改善アイデアを5つ提案してください。
    
    原文書：
    {text}
    
    行動科学分析：
    {east_analysis}
    
    必ずMarkdown表（| 番号 | 改善アイデア |）で5つ出力してください。
    | 番号 | 改善アイデア |
    |------|--------------|
    | ① |  |
    | ② |  |
    | ③ |  |
    | ④ |  |
    | ⑤ |  |
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
st.markdown('<p style="font-size: 0.9em;">このツールは、行動科学の知見に基づき、行政文書やチラシに潜む<span style="color: #0066cc; font-weight: bold;">スラッジ</span>（複雑さ、煩雑さ、難解さといった行動を妨げる要因）を特定し、<span style="color: #0066cc; font-weight: bold;">スラスラ</span>読んで行動できるよう改善するための初期診断ツールです。</p>', unsafe_allow_html=True)

st.markdown('<p style="color: #0066cc; font-weight: bold;">Step1 チラシなどのPDFファイルをアップロードしてください。</p>', unsafe_allow_html=True)
st.markdown('''
<p style="font-size: 0.9em;">
・このツールは、関連ウェブサイトの検索結果も踏まえ、ファイルのターゲット、促したい目標行動、そこに至るまでのプロセスを可視化します。<br>
・次への動作や手順が明確でわかりすいか、情報は必要十分なシンプルなものかを診断、重要な改善ポイントを５つ提示します。<br>
・プロセス全体を最適化するために、このファイル以外の改善アイデアも提示します。
</p>
''', unsafe_allow_html=True)

st.markdown('<p style="color: #0066cc; font-weight: bold;">Step2 あなたは、診断結果を踏まえて実際に改善を行います。</p>', unsafe_allow_html=True)
st.markdown('''
<p style="font-size: 0.9em;">
このツールは、改善スピードを加速化したり、一時的な処置を行うために用意された、あくまでも初期診断ツールです。改善の実行や、さらなる課題の深堀り、プロセス全体の見直しを進めていきましょう。<br>
※ファイル改善例の生成機能については、現在準備中です。
</p>
''', unsafe_allow_html=True)

uploaded_file = st.file_uploader("PDFファイルをアップロードしてください", type=['pdf'])

if uploaded_file is not None:
    with st.spinner("分析中..."):
        # PDFからテキストを抽出
        text = extract_text_from_pdf(uploaded_file)
        if text:
            # 関連情報の検索
            related_info = search_related_info(text)
            
            # ペルソナ分析
            persona = analyze_persona(text, related_info)
            st.subheader("想定されるペルソナ")
            st.markdown(persona)
            
            # 目標行動の分析
            target_action = analyze_target_action(text, persona)
            st.subheader("促したい行動")
            st.markdown(target_action)
            
            # 行動プロセスマップの作成
            process_map = create_action_process_map(text, target_action)
            st.subheader("行動プロセスマップ")
            st.markdown(process_map)
            
            # 行動科学分析
            east_analysis = analyze_east_framework(text, process_map)
            st.subheader("行動科学分析")
            st.markdown(east_analysis)
            
            # 改善案の生成
            improvements = generate_improvement_suggestions(text, east_analysis)
            st.subheader("改善案（重要な改善ポイント5選）")
            st.markdown(improvements)
            
            # プロセス全体の最適化アイデア
            process_ideas = generate_process_optimization_ideas(text, east_analysis)
            st.subheader("プロセス全体の最適化アイデア（このファイル以外）")
            st.markdown(process_ideas)

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
