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

def markdown_to_story_elements(md_text, style, table_style, available_width):
    """
    Converts a markdown string (potentially a table) into a list of ReportLab flowables.
    """
    if not isinstance(md_text, str):
        md_text = str(md_text)

    # Clean up the markdown text
    md_text = md_text.strip()
    lines = [l.strip() for l in md_text.split('\n') if l.strip()]
    
    is_table = False
    if len(lines) > 1 and '|' in lines[0] and '---' in lines[1]:
        is_table = True

    if is_table:
        data = []
        header_line = lines.pop(0)
        separator_line = lines.pop(0) # and remove it

        # Header
        header_cells = [cell.strip() for cell in header_line.strip('|').split('|')]
        data.append([Paragraph(cell, style) for cell in header_cells])

        # Body
        for line in lines:
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            data.append([Paragraph(cell, style) for cell in cells])
        
        if not data:
            return [Paragraph(md_text.replace('\n', '<br/>'), style)]

        try:
            col_widths = [available_width/len(data[0])] * len(data[0])
            table = Table(data, hAlign='LEFT', colWidths=col_widths)
            table.setStyle(table_style)
            return [table]
        except Exception:
             return [Paragraph(md_text.replace('\n', '<br/>'), style)]

    else:
        # Not a table, just return as a paragraph
        return [Paragraph(md_text.replace('\n', '<br/>'), style)]

def generate_pdf_report(filename, persona, target_action, process_map, east_analysis, improvements, process_ideas, user_comment=None, east_analysis_with_comment=None, improvements_with_comment=None):
    """
    PDFレポートを生成する関数
    """
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
        jp_font_name = 'HeiseiMin-W3'
    except Exception:
        jp_font_name = 'Helvetica' # Fallback

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    story = []
    
    # スタイルの設定
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Normal_JP', parent=styles['Normal'], fontName=jp_font_name, fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='Title_JP', parent=styles['h1'], fontName=jp_font_name, fontSize=18, alignment=TA_CENTER, spaceAfter=20))
    styles.add(ParagraphStyle(name='Heading_JP', parent=styles['h2'], fontName=jp_font_name, fontSize=14, spaceBefore=12, spaceAfter=12))
    
    title_style = styles['Title_JP']
    heading_style = styles['Heading_JP']
    normal_style = styles['Normal_JP']

    table_style = TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), jp_font_name),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    
    available_width = doc.width

    # タイトル
    story.append(Paragraph("スラスラ診断レポート", title_style))
    story.append(Spacer(1, 20))
    
    # ファイル名と日時
    story.append(Paragraph(f"<b>ファイル名:</b> {filename}", normal_style))
    story.append(Paragraph(f"<b>診断日時:</b> {datetime.now().strftime('%Y年%m月%d日 %H:%M')}", normal_style))
    story.append(Spacer(1, 20))
    
    # 各セクション
    sections = {
        "想定されるターゲット": persona,
        "目標行動": target_action,
        "行動プロセスマップ": process_map,
        "スラッジ分析": east_analysis,
        "重要な改善ポイント５選": improvements,
        "この文書以外の改善アイデア": process_ideas,
    }

    for title, content in sections.items():
        story.append(Paragraph(title, heading_style))
        story.extend(markdown_to_story_elements(content, normal_style, table_style, available_width))
        story.append(Spacer(1, 15))

    # 再審査結果がある場合
    if user_comment and user_comment.strip():
        story.append(Paragraph("診断結果へのフィードバック", heading_style))
        story.append(Paragraph(f"<b>コメント:</b> {user_comment}", normal_style))
        story.append(Spacer(1, 15))
        
        if east_analysis_with_comment:
            story.append(Paragraph("再審査：スラッジ分析", heading_style))
            story.extend(markdown_to_story_elements(east_analysis_with_comment, normal_style, table_style, available_width))
            story.append(Spacer(1, 15))
        
        if improvements_with_comment:
            story.append(Paragraph("再審査：重要な改善ポイント５選", heading_style))
            story.extend(markdown_to_story_elements(improvements_with_comment, normal_style, table_style, available_width))
            story.append(Spacer(1, 15))
    
    # PDFを生成
    doc.build(story)
    buffer.seek(0)
    return buffer

def get_pdf_download_link(pdf_buffer, filename):
    """
    PDFダウンロードリンクを生成する関数
    """
    b64 = base64.b64encode(pdf_buffer.getvalue()).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="{filename}" target="_blank">PDFレポートをダウンロード</a>'
    return href

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
            
            # セッション状態に結果を保存
            st.session_state['analysis_results'] = {
                'filename': uploaded_file.name,
                'persona': persona,
                'target_action': target_action,
                'process_map': process_map,
                'east_analysis': east_analysis,
                'improvements': improvements,
                'process_ideas': process_ideas
            }
            
            # PDFレポート出力ボタン
            st.markdown("---")
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("PDFレポート出力", type="primary"):
                    if 'analysis_results' in st.session_state:
                        results = st.session_state['analysis_results']
                        pdf_buffer = generate_pdf_report(
                            results['filename'],
                            results['persona'],
                            results['target_action'],
                            results['process_map'],
                            results['east_analysis'],
                            results['improvements'],
                            results['process_ideas']
                        )
                        pdf_filename = f"スラスラ診断レポート_{results['filename'].replace('.pdf', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                        st.markdown(get_pdf_download_link(pdf_buffer, pdf_filename), unsafe_allow_html=True)
            
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
                        st.session_state['reanalysis_results'] = {
                            'user_comment': user_comment,
                            'east_analysis_with_comment': east_analysis_with_comment,
                            'improvements_with_comment': improvements_with_comment
                        }
                        
                        # 再審査後のPDFレポート出力ボタン
                        st.markdown("---")
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            if st.button("再審査結果PDFレポート出力", type="primary"):
                                if 'analysis_results' in st.session_state and 'reanalysis_results' in st.session_state:
                                    results = st.session_state['analysis_results']
                                    reanalysis = st.session_state['reanalysis_results']
                                    pdf_buffer = generate_pdf_report(
                                        results['filename'],
                                        results['persona'],
                                        results['target_action'],
                                        results['process_map'],
                                        results['east_analysis'],
                                        results['improvements'],
                                        results['process_ideas'],
                                        reanalysis['user_comment'],
                                        reanalysis['east_analysis_with_comment'],
                                        reanalysis['improvements_with_comment']
                                    )
                                    pdf_filename = f"スラスラ診断レポート_再審査_{results['filename'].replace('.pdf', '')}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
                                    st.markdown(get_pdf_download_link(pdf_buffer, pdf_filename), unsafe_allow_html=True)
                else:
                    st.warning("コメントを入力してから再審査を開始してください。")

# フッター
st.markdown('<div style="text-align:center; color:gray; margin-top:3em;">Powered by StepSpin 2025</div>', unsafe_allow_html=True) 
