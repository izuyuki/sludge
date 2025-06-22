import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
import os
import PyPDF2
import io
import requests
from bs4 import BeautifulSoup
import json
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import base64
from datetime import datetime
import re

# 環境変数の読み込み
load_dotenv()

# Gemini APIの設定
api_key = os.getenv('GOOGLE_API_KEY')
if not api_key:
    st.error("GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")
    st.stop()

genai.configure(api_key=api_key)

# モデルの設定
model = genai.GenerativeModel('models/gemini-1.5-pro')

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
            page_text = page.extract_text()
            if page_text:
                text += page_text
        if not text.strip():
            st.error("PDFから文章が検出できませんでした。文章が含まれているPDFをアップロードしてください。")
            return None
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

def analyze_east_framework_with_comment(text, process_map, user_comment):
    prompt = f"""
    ユーザーのコメントを踏まえて、スラッジの観点から以下の情報を再分析してください。
    ※ここでは改善案や提案は出さず、分析のみを行ってください。
    
    文書内容：
    {text}
    
    行動プロセスマップ：
    {process_map}
    
    ユーザーコメント：
    {user_comment}
    
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
        st.error(f"再審査のスラッジ分析に失敗しました: {str(e)}")
        return None

def generate_improvement_suggestions_with_comment(text, east_analysis, user_comment):
    prompt = f"""
    ユーザーのコメントを踏まえて、以下の分析結果を基に、文書の改善案を再提案してください：
    
    原文書：
    {text}
    
    スラッジ分析：
    {east_analysis}
    
    ユーザーコメント：
    {user_comment}
    
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
        st.error(f"再審査の改善案の生成に失敗しました: {str(e)}")
        return None

def get_pdf_export_button_html(target_id, filename, button_text):
    button_uuid = f"download-pdf-{hash(filename)}"
    html = f"""
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<button id="{button_uuid}" style="background-color: #0066cc; color: white; border-radius: 4px; border: none; padding: 0.5rem 1rem; cursor: pointer;">
    {button_text}
</button>
<script>
document.getElementById("{button_uuid}").addEventListener("click", function() {{
    const element = document.getElementById('{target_id}');
    if (element) {{
        const opt = {{
            margin:       [0.5, 0.5, 0.5, 0.5],
            filename:     '{filename}',
            image:        {{ type: 'jpeg', quality: 0.98 }},
            html2canvas:  {{ scale: 2, useCORS: true, letterRendering: true, scrollY: 0 }},
            jsPDF:        {{ unit: 'in', format: 'a4', orientation: 'portrait' }},
            pagebreak:    {{ mode: ['avoid-all', 'css', 'legacy'] }}
        }};
        const reportTitle = "スラスラ診断レポート";
        const titleEl = document.createElement('h1');
        titleEl.appendChild(document.createTextNode(reportTitle));
        titleEl.style.textAlign = 'center';
        titleEl.style.fontSize = '2rem';
        titleEl.style.marginBottom = '2rem';
        
        const clonedElement = element.cloneNode(true);
        clonedElement.insertBefore(titleEl, clonedElement.firstChild);

        html2pdf().from(clonedElement).set(opt).save();
    }} else {{
        console.error("Element with id '{target_id}' not found.");
    }}
}});
</script>
"""
    return html

# Streamlit UI
# ロゴの表示
st.image("logo.png", width=100)

st.title("スラスラ診断くん")
st.markdown('行動科学の知見と生成AIにより、行政文書やチラシに潜む<span style="font-weight: bold;">"スラッジ"</span>（複雑さ、煩雑さ、難解さといった行動を妨げる要因）を特定し、<span style="font-weight: bold;">"スラスラ"</span>読んで行動できるよう改善するための初期診断ツールです。', unsafe_allow_html=True)

st.markdown("""
| あなたの行動ステップ | このツールができること |
|---------|-------------------|
| **Step1** チラシなどのPDF文書（１ファイル）をアップロードしてください。 | 文書のターゲット、促したい目標行動、そこに至るプロセスを可視化し、スラッジを特定します。 |
| **Step2** 診断結果を踏まえて、チラシなどを実際に改善してください。 | すぐに取り組める"重要な改善ポイント５選"を提示します。 |
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
            st.markdown('<div id="report-content">', unsafe_allow_html=True)

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
            st.markdown(east_analysis)
            
            # 改善案の生成
            improvements = generate_improvement_suggestions(text, east_analysis)
            st.subheader("重要な改善ポイント５選")
            st.markdown(improvements)
            
            # プロセス全体の最適化アイデア
            process_ideas = generate_process_optimization_ideas(text, east_analysis, process_map)
            st.subheader("この文書以外の改善アイデア")
            st.markdown(process_ideas)
            
            # ユーザーコメント入力欄と再審査機能
            st.markdown("---")
            st.subheader("診断結果へのフィードバック")
            st.markdown("診断結果について、ご意見やご要望があればお聞かせください。")
            
            user_comment = st.text_area("コメントを入力してください（任意）", height=100)
            
            if st.button("再審査スタート", type="primary"):
                if user_comment.strip():
                    with st.spinner("再審査中..."):
                        # ユーザーコメントを踏まえたスラッジ分析
                        east_analysis_with_comment = analyze_east_framework_with_comment(text, process_map, user_comment)
                        st.subheader("再審査：スラッジ分析")
                        st.markdown(east_analysis_with_comment)
                        
                        # ユーザーコメントを踏まえた改善案の生成
                        improvements_with_comment = generate_improvement_suggestions_with_comment(text, east_analysis_with_comment, user_comment)
                        st.subheader("再審査：重要な改善ポイント５選")
                        st.markdown(improvements_with_comment)
                        
                        # セッション状態に再審査結果を保存
                        st.session_state['reanalysis_done'] = True
                else:
                    st.warning("コメントを入力してから再審査を開始してください。")
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("---")

            # PDF出力ボタン
            if st.session_state.get('reanalysis_done', False):
                 pdf_filename = f"スラスラ診断レポート_再審査_{uploaded_file.name.replace('.pdf', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                 st.markdown(get_pdf_export_button_html("report-content", pdf_filename, "再審査結果PDFレポート出力"), unsafe_allow_html=True)
            else:
                 pdf_filename = f"スラスラ診断レポート_{uploaded_file.name.replace('.pdf', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                 st.markdown(get_pdf_export_button_html("report-content", pdf_filename, "PDFレポート出力"), unsafe_allow_html=True)
            
            # Reset flag if new file is uploaded
            if 'last_uploaded_filename' not in st.session_state or st.session_state.last_uploaded_filename != uploaded_file.name:
                st.session_state.reanalysis_done = False
                st.session_state.last_uploaded_filename = uploaded_file.name

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
