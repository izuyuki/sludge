import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import PyPDF2
import io
import requests
from bs4 import BeautifulSoup

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
    
    以下の形式で、各項目100～150字程度で簡潔に出力してください：
    1. 主要なペルソナの特徴
    2. 想定される年齢層
    3. 想定される生活状況
    4. 想定される課題やニーズ
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
    
    以下の形式で出力してください：
    1. 主要な目標行動
    2. 期待される結果
    3. 行動の重要性
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
    
    以下の形式で出力してください：
    1. 行動プロセスの各ステップ
    2. 各ステップでの必要な情報
    3. 文書との接点
    4. 想定される摩擦点
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"行動プロセスマップの作成に失敗しました: {str(e)}")
        return None

def analyze_east_framework(text, process_map):
    prompt = f"""
    EASTフレームワークの観点から、以下の情報を分析してください：
    
    文書内容：
    {text}
    
    行動プロセスマップ：
    {process_map}
    
    以下の観点で分析してください：
    1. Easy（簡単さ）
       - 5W1Hの明確性
       - 情報の簡潔さ
       - 理解のしやすさ
    2. Attractive（魅力的さ）
       - デザインの適切性
       - 情報の整理
    3. Social（社会的）
       - 社会的影響
       - コミュニティの関与
    4. Timely（タイミング）
       - 情報提供の適切な時期
       - 行動のタイミング
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"EASTフレームワーク分析に失敗しました: {str(e)}")
        return None

def generate_improvement_suggestions(text, east_analysis):
    prompt = f"""
    以下の分析結果を基に、文書の改善案を提案してください：
    
    原文書：
    {text}
    
    EAST分析：
    {east_analysis}
    
    以下の形式で出力してください：
    1. 改善のポイント
    2. 具体的な改善案
    3. 期待される効果
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"改善案の生成に失敗しました: {str(e)}")
        return None

# Streamlit UI
# ロゴの表示
st.image("logo.png", width=50)

st.title("スラスラ診断くん")
st.markdown('<p style="font-size: 0.9em;">このツールは、行動科学の知見に基づき、行政文書やチラシに潜む"スラッジ"（複雑さ、煩雑さ、難解さといった行動を妨げる要因）を特定し、スラスラ読んで行動できるよう改善するための初期診断ツールです。</p>', unsafe_allow_html=True)

st.subheader("使い方")
st.markdown("**Step1 チラシなどのPDFファイルをアップロードしてください。**")
st.write("　このツールは、関連ウェブサイトの検索結果も踏まえ、ファイルのターゲット、促したい目標行動、そこに至るまでのプロセスを可視化し、次のプロセスへの動作や手順が明確でわかりすいか、必要十分な内容かを診断し、重要な改善ポイントを５つ提示します。また、プロセス全体を最適化するために、このファイル以外の改善アイデアも提示します。")

st.markdown("**Step2 あなたは、診断結果を踏まえて実際に改善を行います。**")
st.write("　このツールは、改善スピードを加速化するために用意された、あくまでも初期診断ツールです。改善の実行や、さらなる課題の深堀り、プロセス全体の見直しを進めていきましょう。")
st.write("　※ファイル改善例の生成機能については、現在準備中です。")

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
            st.write(persona)
            
            # 目標行動の分析
            target_action = analyze_target_action(text, persona)
            st.subheader("促したい行動")
            st.write(target_action)
            
            # 行動プロセスマップの作成
            process_map = create_action_process_map(text, target_action)
            st.subheader("行動プロセスマップ")
            st.write(process_map)
            
            # EASTフレームワーク分析
            east_analysis = analyze_east_framework(text, process_map)
            st.subheader("EASTフレームワーク分析")
            st.write(east_analysis)
            
            # 改善案の生成
            improvements = generate_improvement_suggestions(text, east_analysis)
            st.subheader("改善案")
            st.write(improvements)

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
