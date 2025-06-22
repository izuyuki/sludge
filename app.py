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
import datetime

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

def generate_pdf_report(persona, target_action, process_map, east_analysis, improvements, process_ideas, original_text):
    """診断結果をPDFレポートとして生成する"""
    try:
        # PDFファイルを作成
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        
        # スタイルの設定
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkblue
        )
        normal_style = styles['Normal']
        
        # タイトル
        story.append(Paragraph("スラスラ診断くん 診断レポート", title_style))
        story.append(Spacer(1, 20))
        
        # 診断日時
        current_time = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
        story.append(Paragraph(f"診断日時: {current_time}", normal_style))
        story.append(Spacer(1, 20))
        
        # 原文書の要約（最初の200文字）
        story.append(Paragraph("原文書の要約", heading_style))
        summary_text = original_text[:200] + "..." if len(original_text) > 200 else original_text
        story.append(Paragraph(summary_text, normal_style))
        story.append(Spacer(1, 15))
        
        # 想定されるターゲット
        story.append(Paragraph("想定されるターゲット", heading_style))
        story.append(Paragraph(persona, normal_style))
        story.append(Spacer(1, 15))
        
        # 目標行動
        story.append(Paragraph("目標行動", heading_style))
        story.append(Paragraph(target_action, normal_style))
        story.append(Spacer(1, 15))
        
        # 行動プロセスマップ
        story.append(Paragraph("行動プロセスマップ", heading_style))
        story.append(Paragraph(process_map, normal_style))
        story.append(Spacer(1, 15))
        
        # スラッジ分析
        story.append(Paragraph("スラッジ分析", heading_style))
        story.append(Paragraph(east_analysis, normal_style))
        story.append(Spacer(1, 15))
        
        # 重要な改善ポイント５選
        story.append(Paragraph("重要な改善ポイント５選", heading_style))
        story.append(Paragraph(improvements, normal_style))
        story.append(Spacer(1, 15))
        
        # この文書以外の改善アイデア
        story.append(Paragraph("この文書以外の改善アイデア", heading_style))
        story.append(Paragraph(process_ideas, normal_style))
        story.append(Spacer(1, 20))
        
        # フッター
        story.append(Paragraph("Powered by StepSpin 2025", normal_style))
        
        # PDFを生成
        doc.build(story)
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        st.error(f"PDFの生成に失敗しました: {str(e)}")
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
            
            # 診断結果をセッション状態に保存
            st.session_state.diagnosis_complete = True
            st.session_state.diagnosis_results = {
                'persona': persona,
                'target_action': target_action,
                'process_map': process_map,
                'east_analysis': east_analysis,
                'improvements': improvements,
                'process_ideas': process_ideas,
                'original_text': text
            }

# 診断が完了した場合、PDF出力ボタンを表示
if st.session_state.get('diagnosis_complete', False):
    st.markdown("---")
    st.subheader("📄 診断レポート出力")
    st.markdown("診断結果をPDFレポートとしてダウンロードできます。")
    
    if st.button("診断レポート出力", type="primary"):
        with st.spinner("PDFを生成中..."):
            results = st.session_state.diagnosis_results
            pdf_buffer = generate_pdf_report(
                results['persona'],
                results['target_action'],
                results['process_map'],
                results['east_analysis'],
                results['improvements'],
                results['process_ideas'],
                results['original_text']
            )
            
            if pdf_buffer:
                # ファイル名を生成（現在の日時を含む）
                current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"スラスラ診断レポート_{current_time}.pdf"
                
                # PDFをダウンロード可能にする
                st.download_button(
                    label="📥 PDFをダウンロード",
                    data=pdf_buffer.getvalue(),
                    file_name=filename,
                    mime="application/pdf",
                    type="primary"
                )
                st.success("PDFレポートが生成されました。上記のボタンからダウンロードしてください。")

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
