import streamlit as st


def inject_styles():
    st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css');

:root{
  --brand:#2563EB;
  --brand-dark:#1D4ED8;
  --soft:#EFF6FF;
  --ink:#111827;
  --sub:#374151;
  --muted:#6B7280;
  --line:#E5E7EB;
  --canvas:#F5F7FA;
}
html,body,.stApp,button,input,select,textarea{
  font-family:'Pretendard',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic',sans-serif!important;
}
html,body,.stApp{background:var(--canvas);color:var(--ink);overflow-x:hidden!important}
.stApp a,.stApp a:visited,.stApp a:hover{text-decoration:none!important}
.block-container{max-width:1180px;padding:1.15rem 1rem 4rem;box-sizing:border-box}

#MainMenu,footer,header,header[data-testid="stHeader"],[data-testid="stHeader"],[data-testid="stAppHeader"],
[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],
.viewerBadge_container__r5tak,.styles_viewerBadge__CvC9N{
  display:none!important;visibility:hidden!important;height:0!important;max-height:0!important;min-height:0!important;
  border:0!important;box-shadow:none!important;background:transparent!important;
}
[data-testid="stElementContainer"]:has(iframe[height="0"]),[data-testid="stIFrame"]:has(iframe[height="0"]){
  display:none!important;height:0!important;margin:0!important;padding:0!important;
}
.stApp,[data-testid="stAppViewContainer"],[data-testid="stMain"],section.main,[data-testid="stMainBlockContainer"]{
  padding-top:0!important;margin-top:0!important;border-top:0!important;outline:0!important;box-shadow:none!important;
}
.stApp::before,.stApp::after,[data-testid="stAppViewContainer"]::before,[data-testid="stAppViewContainer"]::after,
[data-testid="stMain"]::before,[data-testid="stMain"]::after,section.main::before,section.main::after{
  display:none!important;content:none!important;border:0!important;box-shadow:none!important;
}

/* 상단 브랜드 헤더 */
.top-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;padding:2px}
.brand-wrap{display:inline-flex;align-items:center;gap:9px;text-decoration:none!important;color:inherit!important}
.brand-logo{display:inline-flex;align-items:center;justify-content:center;width:33px;height:33px;border-radius:10px;background:#111827;color:#fff;font-size:15px;font-weight:800;box-shadow:0 3px 10px rgba(17,24,39,.14)}
.brand-name{font-size:20px;font-weight:850;letter-spacing:-.03em;color:var(--ink)}
.brand-en{font-size:10.5px;font-weight:750;letter-spacing:.09em;color:#4B5563;background:#EAEFF5;padding:3px 8px;border-radius:999px}
.top-sub{font-size:13px;font-weight:600;color:var(--muted);letter-spacing:-.01em}

/* 히어로 배너 */
.hero-banner{
  background:linear-gradient(135deg,#FFFFFF 0%,#F8FAFC 65%,#F1F5FD 100%);
  border:1px solid #E2E8F0;
  border-radius:18px;
  padding:20px 22px;
  margin-bottom:12px;
  box-shadow:0 4px 18px rgba(15,23,42,.03);
}
.hero-kicker{font-size:12px;font-weight:700;color:var(--brand);letter-spacing:-.01em;margin-bottom:5px}
.hero-headline{font-size:21px;font-weight:800;letter-spacing:-.025em;color:var(--ink);line-height:1.35}
.hero-headline b{color:var(--brand);font-weight:850}
.hero-stats{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-top:12px}
.stat-pill{display:inline-flex;align-items:center;gap:5px;background:#FFFFFF;border:1px solid #E2E8F0;padding:5px 11px;border-radius:999px;font-size:12.5px;font-weight:650;color:var(--sub);white-space:nowrap}
.stat-pill strong{color:var(--ink);font-weight:800}
.live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#1F9D63}

/* 검색(3) : 카테고리(1) 단일 행 필터 바 */
.st-key-filter_bar [data-testid="stHorizontalBlock"]{
  display:grid!important;
  grid-template-columns:3fr 1fr!important;
  gap:8px!important;
  align-items:center!important;
  width:100%!important;
  margin:0!important;
}
.st-key-filter_bar [data-testid="stColumn"],
.st-key-filter_bar [data-testid="column"]{
  width:100%!important;
  min-width:0!important;
  padding:0!important;
  margin:0!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"],
div[data-testid="stSelectbox"] div[data-baseweb="select"]{
  border:1px solid #D5DCE6!important;
  outline:0!important;
  background:#fff!important;
  box-shadow:0 1px 4px rgba(15,23,42,.025)!important;
  border-radius:12px!important;
  transition:border-color .15s,box-shadow .15s!important;
}
div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus-within{
  border-color:#2563EB!important;
  box-shadow:0 0 0 3px rgba(37,99,235,.1)!important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] div[role="combobox"] *{
  background:#fff!important;
  color:var(--ink)!important;
  -webkit-text-fill-color:var(--ink)!important;
  border:0!important;
  outline:0!important;
  font-size:14px!important;
}
div[data-testid="stSelectbox"] div[role="combobox"],
div[data-testid="stSelectbox"] input{
  cursor:pointer!important;
  user-select:none!important;
  -webkit-user-select:none!important;
  caret-color:transparent!important;
}
div[data-testid="stSelectbox"] svg{fill:var(--sub)!important;color:var(--sub)!important}

/* 결과 카운트 & 우측 '내돈내산' 원형 체크 토글 행 */
.st-key-result_bar{margin:8px 0 11px!important}
.st-key-result_bar [data-testid="stHorizontalBlock"]{
  display:flex!important;
  flex-direction:row!important;
  flex-wrap:nowrap!important;
  align-items:center!important;
  justify-content:space-between!important;
  gap:8px!important;
  width:100%!important;
  margin:0!important;
}
.st-key-result_bar [data-testid="stColumn"],
.st-key-result_bar [data-testid="column"]{
  flex:0 1 auto!important;
  width:auto!important;
  min-width:0!important;
  padding:0!important;
}
.st-key-result_bar [data-testid="stColumn"]:last-child,
.st-key-result_bar [data-testid="column"]:last-child{
  margin-left:auto!important;
  display:flex!important;
  justify-content:flex-end!important;
}
.result-count-text{
  font-size:13.5px;
  color:var(--sub);
  font-weight:600;
  line-height:34px;
  padding-left:2px;
  white-space:nowrap;
}
.result-count-text b{color:var(--ink);font-weight:800}

.st-key-self_buy_toggle{display:flex!important;justify-content:flex-end!important}
.st-key-self_buy_toggle button{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  width:auto!important;
  min-height:34px!important;
  height:34px!important;
  padding:0 13px!important;
  border-radius:999px!important;
  font-size:13px!important;
  font-weight:700!important;
  line-height:1.2!important;
  white-space:nowrap!important;
  box-shadow:0 1px 3px rgba(15,23,42,.03)!important;
  transition:all .15s ease!important;
}
.st-key-self_buy_toggle button::before{
  content:""!important;
  display:inline-block!important;
  width:15px!important;
  height:15px!important;
  border-radius:50%!important;
  margin-right:7px!important;
  flex-shrink:0!important;
  box-sizing:border-box!important;
  transition:all .15s ease!important;
}
.st-key-self_buy_toggle button[kind="secondary"]{
  background:#FFFFFF!important;
  border:1px solid #D5DCE6!important;
  color:#374151!important;
}
.st-key-self_buy_toggle button[kind="secondary"]:hover{
  border-color:#16A34A!important;
  color:#14532D!important;
  background:#F8FDF9!important;
}
.st-key-self_buy_toggle button[kind="secondary"]::before{
  border:1.8px solid #9CA3AF!important;
  background:#FFFFFF!important;
}
.st-key-self_buy_toggle button[kind="secondary"]:hover::before{
  border-color:#16A34A!important;
}
.st-key-self_buy_toggle button[kind="primary"]{
  background:#ECFDF5!important;
  border:1.5px solid #16A34A!important;
  color:#14532D!important;
  font-weight:800!important;
}
.st-key-self_buy_toggle button[kind="primary"]:hover{
  background:#DCFCE7!important;
  border-color:#15803D!important;
}
.st-key-self_buy_toggle button[kind="primary"]::before{
  border:1.8px solid #16A34A!important;
  background:#16A34A!important;
  box-shadow:inset 0 0 0 2.8px #ECFDF5!important;
}

/* 기본 버튼 & 폼 */
.stButton>button,.stLinkButton>a{min-height:39px!important;border-radius:10px!important;font-weight:700!important;font-size:13px!important;transition:all .15s!important}
.stButton>button[kind="primary"],.stLinkButton>a[kind="primary"]{background:#111827!important;border-color:#111827!important;color:#fff!important}
.stButton>button[kind="primary"]:hover,.stLinkButton>a[kind="primary"]:hover{background:#2563EB!important;border-color:#2563EB!important}
.stButton>button[kind="secondary"],.stLinkButton>a[kind="secondary"]{background:#F3F5F8!important;border:1px solid #E2E8F0!important;color:#374151!important}
.stButton>button[kind="secondary"]:hover,.stLinkButton>a[kind="secondary"]:hover{background:#E9EDF3!important}

div[data-testid="stForm"]{border:1px solid #E2E8F2!important;background:#F9FAFC!important;border-radius:14px!important;padding:16px!important}
div[data-testid="stForm"] input,div[data-testid="stForm"] textarea,div[data-testid="stForm"] div[role="combobox"]{background:#fff!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important}

/* 상품 그리드: 행(Row) 기준 세로 높이 통일 + 상·하·좌·우 12px 완전 대칭 여백 */
.st-key-product_grid,.st-key-related_grid{width:100%!important;max-width:100%!important;box-sizing:border-box!important}
.st-key-product_grid [data-testid="stHorizontalBlock"],
.st-key-related_grid [data-testid="stHorizontalBlock"]{
  display:flex!important;
  gap:16px!important;
  align-items:stretch!important;
  width:100%!important;
  max-width:100%!important;
  margin:0 0 16px 0!important;
  padding:0!important;
  box-sizing:border-box!important;
}
.st-key-product_grid [data-testid="stColumn"],
.st-key-product_grid [data-testid="column"],
.st-key-related_grid [data-testid="stColumn"],
.st-key-related_grid [data-testid="column"]{
  flex:1 1 0%!important;
  width:0!important;
  min-width:0!important;
  padding:0!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:stretch!important;
  box-sizing:border-box!important;
}
.st-key-product_grid [data-testid="stColumn"] > div,
.st-key-product_grid [data-testid="column"] > div,
.st-key-product_grid [data-testid="stVerticalBlock"],
.st-key-product_grid [data-testid="stElementContainer"],
.st-key-product_grid [data-testid="stMarkdownContainer"],
.st-key-product_grid [data-testid="stMarkdownContainer"] > div,
.st-key-related_grid [data-testid="stColumn"] > div,
.st-key-related_grid [data-testid="column"] > div,
.st-key-related_grid [data-testid="stVerticalBlock"],
.st-key-related_grid [data-testid="stElementContainer"],
.st-key-related_grid [data-testid="stMarkdownContainer"],
.st-key-related_grid [data-testid="stMarkdownContainer"] > div{
  flex:1 1 auto!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:stretch!important;
  height:100%!important;
  min-height:100%!important;
  width:100%!important;
  margin:0!important;
  padding:0!important;
}

.product-card{
  flex:1 1 auto!important;
  display:flex!important;
  flex-direction:column!important;
  width:100%!important;
  height:100%!important;
  padding:12px!important;
  margin:0!important;
  gap:10px!important;
  background:#FFFFFF!important;
  border:1px solid #E2E8F0!important;
  border-radius:16px!important;
  box-shadow:0 2px 10px rgba(15,23,42,.03)!important;
  box-sizing:border-box!important;
  transition:transform .18s ease,border-color .18s ease,box-shadow .18s ease!important;
}
.product-card:hover{
  transform:translateY(-2px)!important;
  border-color:#CBD5E1!important;
  box-shadow:0 10px 26px rgba(15,23,42,.08)!important;
}
.product-card:hover .product-title,
.product-card:hover .related-name{
  color:#1D4ED8!important;
}

/* 썸네일 (클릭 시 상세페이지 이동, 영상 배지 클릭 시 유튜브 이동) */
.video-thumbnail-wrap{
  position:relative!important;
  display:block!important;
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:10px!important;
  border:1px solid rgba(15,23,42,.07)!important;
  background:#F1F3F6!important;
  overflow:hidden!important;
  box-sizing:border-box!important;
  flex-shrink:0!important;
}
.card-thumb-link{
  display:block!important;
  width:100%!important;
  height:100%!important;
  cursor:pointer!important;
  text-decoration:none!important;
}
.video-thumbnail{
  display:block!important;
  width:100%!important;
  height:100%!important;
  object-fit:cover!important;
  object-position:center center!important;
  transition:transform .24s ease!important;
}
.product-card:hover .video-thumbnail{
  transform:scale(1.025);
}
.thumb-video-badge{
  position:absolute!important;
  right:8px!important;
  bottom:8px!important;
  z-index:10!important;
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  gap:4px!important;
  padding:4px 10px!important;
  border-radius:999px!important;
  background:rgba(17,24,39,.86)!important;
  border:1px solid rgba(255,255,255,.2)!important;
  color:#FFFFFF!important;
  font-size:11px!important;
  font-weight:750!important;
  line-height:1.2!important;
  letter-spacing:-.01em!important;
  text-decoration:none!important;
  backdrop-filter:blur(6px);
  transition:background-color .15s ease,transform .15s ease!important;
}
.thumb-video-badge:hover{
  background:#DC2626!important;
  transform:scale(1.03);
}
.product-placeholder{
  position:relative!important;
  width:100%!important;
  aspect-ratio:16 / 9!important;
  margin:0!important;
  border-radius:10px!important;
  border:1px solid rgba(15,23,42,.06)!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:center!important;
  justify-content:center!important;
  gap:4px!important;
  overflow:hidden!important;
  box-sizing:border-box!important;
}
.product-placeholder span{font-size:13.5px;font-weight:850;letter-spacing:.12em}
.product-placeholder small{font-size:12px;font-weight:700;opacity:.9}

/* 카드 본문 전체 클릭 링크 (남은 높이를 채워 하단 버튼을 행 최하단으로 정렬) */
.card-body-link{
  flex:1 1 auto!important;
  display:flex!important;
  flex-direction:column!important;
  align-items:stretch!important;
  gap:8px!important;
  padding:0!important;
  margin:0!important;
  width:100%!important;
  box-sizing:border-box!important;
  color:inherit!important;
  text-decoration:none!important;
  cursor:pointer!important;
}
.card-source-bar{
  display:flex!important;
  flex-direction:row!important;
  align-items:center!important;
  justify-content:space-between!important;
  gap:8px!important;
  width:100%!important;
  height:18px!important;
  min-width:0!important;
  padding:0!important;
  margin:0!important;
}
.source-chip{
  display:inline-flex!important;
  align-items:center!important;
  gap:5px!important;
  height:18px!important;
  min-width:0!important;
  max-width:62%!important;
  padding:0!important;
  background:transparent!important;
  color:#374151!important;
  font-size:12px!important;
  font-weight:700!important;
  line-height:1.2!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
}
.source-chip b{color:#DC2626;font-size:9px;flex-shrink:0}
.brand-eyebrow{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:flex-end!important;
  height:18px!important;
  margin-left:auto!important;
  padding:0!important;
  font-size:12px!important;
  font-weight:650!important;
  color:#6B7280!important;
  line-height:1.2!important;
  letter-spacing:-.01em!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
  text-align:right!important;
  flex-shrink:0!important;
}

/* 상품명 */
.product-title{
  font-size:15.5px!important;
  font-weight:800!important;
  color:#111827!important;
  line-height:1.35!important;
  letter-spacing:-.02em!important;
  margin:0!important;
  padding:0!important;
  display:-webkit-box!important;
  -webkit-line-clamp:2!important;
  -webkit-box-orient:vertical!important;
  overflow:hidden!important;
  word-break:keep-all!important;
  text-decoration:none!important;
  transition:color .15s ease!important;
}

/* 1줄 가로 정렬 메타 배지 행 */
.card-meta-row{
  display:flex!important;
  flex-direction:row!important;
  flex-wrap:nowrap!important;
  align-items:center!important;
  gap:6px!important;
  width:100%!important;
  padding:0!important;
  margin:0!important;
  overflow:hidden!important;
}
.badge{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  height:24px!important;
  color:#1E293B!important;
  background:#F1F5F9!important;
  padding:0 8px!important;
  border-radius:6px!important;
  font-size:11.5px!important;
  font-weight:700!important;
  line-height:1.2!important;
  white-space:nowrap!important;
  flex-shrink:0!important;
}
.purchase-dot{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  gap:4px!important;
  height:24px!important;
  padding:0 8px!important;
  border-radius:6px!important;
  font-size:11.5px!important;
  font-weight:700!important;
  line-height:1.2!important;
  white-space:nowrap!important;
  flex-shrink:0!important;
}
.purchase-dot i{display:inline-block!important;width:5.5px!important;height:5.5px!important;border-radius:50%!important;flex-shrink:0!important}
.purchase-buy{color:#14532D!important;background:#DCFCE7!important}.purchase-buy i{background:#16A34A!important}
.purchase-provided{color:#713F12!important;background:#FEF9C3!important}.purchase-provided i{background:#CA8A04!important}
.purchase-ad,.purchase-unknown{color:#7F1D1D!important;background:#FEE2E2!important}.purchase-ad i,.purchase-unknown i{background:#DC2626!important}

/* 고대비 장단점 요약 */
.card-summary-wrap{
  display:flex!important;
  flex-direction:column!important;
  gap:5px!important;
  width:100%!important;
  padding:0!important;
  margin:0!important;
}
.summary-line{
  display:flex!important;
  flex-direction:row!important;
  align-items:center!important;
  gap:7px!important;
  width:100%!important;
  height:32px!important;
  margin:0!important;
  padding:0 9px!important;
  border-radius:8px!important;
  font-size:12.5px!important;
  font-weight:600!important;
  line-height:1.2!important;
  white-space:nowrap!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
  text-decoration:none!important;
  box-sizing:border-box!important;
}
.summary-text{
  min-width:0!important;
  overflow:hidden!important;
  text-overflow:ellipsis!important;
  white-space:nowrap!important;
  color:#1F2937!important;
  text-decoration:none!important;
}
.sum-tag{
  display:inline-flex!important;
  align-items:center!important;
  justify-content:center!important;
  height:18px!important;
  padding:0 6px!important;
  border-radius:4px!important;
  font-size:10.5px!important;
  font-weight:800!important;
  line-height:1.2!important;
  flex-shrink:0!important;
  letter-spacing:-.02em!important;
}
.summary-pro{background:#F0F9F4!important;border:1px solid #DCF2E5!important}
.sum-tag-pro{background:#BBF7D0!important;color:#14532D!important}
.summary-con{background:#FDF3F3!important;border:1px solid #F8DFDF!important}
.sum-tag-con{background:#FECACA!important;color:#7F1D1D!important}
.summary-reason{background:#F4F6F9!important;border:1px solid #E5E9F0!important}
.sum-tag-fit{background:#DCE3EC!important;color:#1E293B!important}

/* 쇼핑몰 버튼 (하단 12px 여백 위에 고정 정렬) */
.shop-btn-grid{
  display:grid!important;
  grid-template-columns:repeat(2,minmax(0,1fr))!important;
  gap:6px!important;
  width:100%!important;
  margin:auto 0 0 0!important;
  padding:0!important;
  flex-shrink:0!important;
  box-sizing:border-box!important;
}
.shop-btn-grid.cols-1{grid-template-columns:minmax(0,1fr)!important}
.shop-btn-grid.cols-3{grid-template-columns:repeat(3,minmax(0,1fr))!important}
.shop-btn{
  display:flex!important;
  align-items:center!important;
  justify-content:center!important;
  width:100%!important;
  min-width:0!important;
  height:38px!important;
  padding:0 8px!important;
  border-radius:8px!important;
  font-size:13px!important;
  font-weight:750!important;
  line-height:1.2!important;
  text-align:center!important;
  text-decoration:none!important;
  white-space:nowrap!important;
  letter-spacing:-.02em!important;
  box-sizing:border-box!important;
  transition:background-color .15s ease,transform .12s ease!important;
}
.shop-btn:active{transform:scale(0.99)}
.shop-btn-naver{background:#1F9D63!important;border:1px solid #1C8E59!important;color:#FFFFFF!important}
.shop-btn-naver:hover{background:#188553!important}
.shop-btn-coupang{background:#D64545!important;border:1px solid #C53B3B!important;color:#FFFFFF!important}
.shop-btn-coupang:hover{background:#BE3838!important}
.shop-btn-oliveyoung{background:#6E9B26!important;border:1px solid #618A20!important;color:#FFFFFF!important}
.shop-btn-oliveyoung:hover{background:#5C831E!important}
.shop-btn-musinsa{background:#1E2229!important;border:1px solid #15181E!important;color:#FFFFFF!important}
.shop-btn-musinsa:hover{background:#111317!important}
.shop-btn-29cm{background:#333945!important;border:1px solid #282D37!important;color:#FFFFFF!important}
.shop-btn-29cm:hover{background:#232831!important}
.shop-btn-zigzag{background:#C94A96!important;border:1px solid #B63E86!important;color:#FFFFFF!important}
.shop-btn-zigzag:hover{background:#B23B82!important}
.shop-btn-ably{background:#DE5462!important;border:1px solid #CC4755!important;color:#FFFFFF!important}
.shop-btn-ably:hover{background:#C74250!important}

/* 상세 비교 페이지 스타일 */
.detail-breadcrumb{font-size:12.5px;font-weight:650;color:var(--muted);margin:2px 0 8px}
.detail-hero-card{
  background:#FFFFFF;
  border:1px solid #E2E8F0;
  border-radius:16px;
  padding:18px;
  margin-bottom:12px;
  box-shadow:0 2px 12px rgba(15,23,42,.03);
}
.detail-brand-line{font-size:13.5px;font-weight:750;color:var(--brand);margin-bottom:4px}
.detail-title{font-size:23px;font-weight:850;color:var(--ink);line-height:1.32;letter-spacing:-.025em;margin-bottom:9px;word-break:keep-all}
.detail-badges{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px}
.trust-box{
  background:#F8FAFC;
  border:1px solid #E2E8F0;
  border-radius:12px;
  padding:11px 13px;
  margin-bottom:12px;
}
.trust-box-head{display:flex;justify-content:space-between;align-items:center;font-size:12.5px;font-weight:750;color:var(--sub);margin-bottom:6px}
.trust-bar{display:flex;height:7px;border-radius:999px;overflow:hidden;background:#E5E9F0;margin-bottom:6px}
.trust-seg-buy{background:#1F9D63}.trust-seg-prov{background:#CA8A04}.trust-seg-ad{background:#D64545}.trust-seg-unk{background:#94A3B8}
.trust-legend{display:flex;flex-wrap:wrap;gap:10px;font-size:12px;font-weight:650;color:var(--sub)}

.danawa-box{border:1px solid #DFE6F0;border-radius:13px;background:#FFFFFF;overflow:hidden}
.danawa-head{display:flex;align-items:center;justify-content:space-between;padding:9px 13px;background:#F6F8FC;border-bottom:1px solid #E6ECF4;font-size:13px;font-weight:800;color:var(--ink)}
.danawa-head span:last-child{font-size:11.5px;font-weight:600;color:var(--muted)}
.danawa-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 13px;border-bottom:1px solid #F1F4F8}
.danawa-row:last-child{border-bottom:0}
.danawa-row:hover{background:#FAFBFD}
.danawa-mall-info{display:flex;align-items:center;gap:9px;min-width:0;flex:1}
.mall-pill{display:inline-flex;align-items:center;justify-content:center;min-width:74px;height:26px;padding:0 9px;border-radius:7px;font-size:11.5px;font-weight:800;color:#FFFFFF;flex-shrink:0}
.mall-pill-naver{background:#1F9D63}.mall-pill-coupang{background:#D64545}.mall-pill-oliveyoung{background:#6E9B26}
.mall-pill-musinsa{background:#1E2229}.mall-pill-29cm{background:#333945}.mall-pill-zigzag{background:#C94A96}.mall-pill-ably{background:#DE5462}
.danawa-desc-wrap{min-width:0;display:flex;flex-direction:column;gap:2px}
.danawa-tag-row{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.danawa-status-tag{font-size:12px;font-weight:750;color:var(--ink)}
.danawa-partner-badge{font-size:10px;font-weight:750;color:#1D4ED8;background:#EFF6FF;padding:1px 6px;border-radius:999px}
.danawa-benefit{font-size:11.5px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.danawa-go-btn{flex-shrink:0;display:inline-flex;align-items:center;justify-content:center;height:34px;padding:0 13px;border-radius:8px;background:#111827;color:#FFFFFF!important;font-size:12px;font-weight:750;text-decoration:none!important;transition:background-color .15s}
.danawa-go-btn:hover{background:#2563EB}

.detail-section{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;padding:16px 18px;margin-bottom:12px;box-shadow:0 2px 12px rgba(15,23,42,.025)}
.detail-section-title{font-size:16.5px;font-weight:800;color:var(--ink);margin:0 0 11px;display:flex;align-items:center;justify-content:space-between}
.detail-section-sub{font-size:12px;font-weight:600;color:var(--muted)}

.recommend-fit-list{display:flex;flex-direction:column;gap:6px}
.recommend-fit-item{background:#F5F8FD;border:1px solid #E1EAFB;color:#1E3A8A;padding:10px 13px;border-radius:10px;font-size:13.5px;font-weight:650;line-height:1.45;word-break:keep-all}

.pros-cons-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.pc-col{border-radius:12px;padding:13px}
.pc-col-pro{background:#F4FAF6;border:1px solid #D7EDE0}
.pc-col-con{background:#FCF6F6;border:1px solid #F5DADA}
.pc-col-title{font-size:14px;font-weight:800;margin-bottom:8px}
.pc-col-pro .pc-col-title{color:#166534}
.pc-col-con .pc-col-title{color:#991B1B}
.pc-item{font-size:13px;line-height:1.45;padding:5px 0;border-bottom:1px dashed rgba(15,23,42,.08);word-break:keep-all;color:#1F2937}
.pc-item:last-child{border-bottom:0;padding-bottom:0}
.pc-count{display:inline-block;margin-left:5px;padding:1px 6px;border-radius:999px;font-size:11px;font-weight:750;background:rgba(255,255,255,.9)}

.matrix-scroll{width:100%;overflow-x:auto;border:1px solid #E6ECF4;border-radius:12px}
.creator-matrix{width:100%;border-collapse:collapse;font-size:13px;min-width:620px}
.creator-matrix th{background:#F7F9FC;color:var(--sub);font-weight:750;text-align:left;padding:10px 12px;border-bottom:1px solid #E6EAF0;white-space:nowrap}
.creator-matrix td{padding:10px 12px;border-bottom:1px solid #F1F4F8;vertical-align:top;line-height:1.45;color:var(--ink);word-break:keep-all}
.creator-matrix tr:last-child td{border-bottom:0}

/* 유튜버 · 영상별 상세 리뷰 비교 카드 */
.creator-review-card{
  display:flex;
  align-items:flex-start;
  gap:14px;
  border:1px solid #E2E8F0;
  background:#FAFBFD;
  border-radius:13px;
  padding:13px;
  margin-bottom:10px;
  transition:border-color .15s ease,background-color .15s ease,box-shadow .15s ease;
}
.creator-review-card:last-child{margin-bottom:0}
.creator-review-card:hover{
  border-color:#CBD5E1;
  background:#FFFFFF;
  box-shadow:0 6px 18px rgba(15,23,42,.05);
}
.creator-thumb-box{
  flex-shrink:0;
  width:210px;
  aspect-ratio:16 / 9;
  border-radius:10px;
  overflow:hidden;
  border:1px solid rgba(15,23,42,.08);
  background:#E9EDF3;
}
.creator-thumb-link{display:block;width:100%;height:100%}
.creator-thumb-img{width:100%;height:100%;object-fit:cover;display:block}
.creator-review-body{flex:1;min-width:0}
.creator-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:4px;flex-wrap:wrap}
.creator-name-wrap{display:flex;align-items:center;flex-wrap:wrap;gap:6px}
.creator-name{font-size:15px;font-weight:800;color:var(--ink)}
.creator-stat{font-size:12px;font-weight:650;color:var(--muted)}
.creator-video-btn{display:inline-flex;align-items:center;gap:4px;padding:5px 11px;border-radius:999px;background:#111827;color:#FFFFFF!important;font-size:11.5px;font-weight:750;text-decoration:none!important}
.creator-video-btn:hover{background:#DC2626}
.creator-video-title{font-size:13px;font-weight:650;color:var(--sub);margin-bottom:6px;line-height:1.4}
.creator-reason{font-size:13.5px;font-weight:700;color:var(--ink);margin-bottom:6px;line-height:1.45;word-break:keep-all}
.creator-evidence{background:#FFFFFF;border-left:3px solid #2563EB;padding:8px 11px;border-radius:0 8px 8px 0;font-size:12.5px;color:#374151;line-height:1.45;margin-bottom:7px;word-break:keep-all}
.creator-tags{display:flex;flex-wrap:wrap;gap:5px}
.ctag-pro{background:#DCFCE7;color:#14532D;padding:3px 9px;border-radius:7px;font-size:11.5px;font-weight:700}
.ctag-con{background:#FEE2E2;color:#7F1D1D;padding:3px 9px;border-radius:7px;font-size:11.5px;font-weight:700}

.related-brand{font-size:12px;font-weight:700;color:#4B5563;text-decoration:none!important}
.related-name{font-size:14.5px;font-weight:800;color:#111827;line-height:1.38;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;word-break:keep-all;text-decoration:none!important;transition:color .15s ease}

.st-key-pagination_bar{margin:10px 0 4px!important}
.st-key-pagination_bar [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;justify-content:center!important;align-items:center!important;gap:6px!important;width:100%!important;max-width:460px!important;margin:0 auto!important}
.st-key-pagination_bar [data-testid="stColumn"],.st-key-pagination_bar [data-testid="column"]{flex:0 0 auto!important;width:auto!important;min-width:38px!important;max-width:none!important;padding:0!important;margin:0!important}
.st-key-pagination_bar .stButton>button{min-width:38px!important;min-height:38px!important;padding:0 11px!important;border-radius:10px!important;font-size:13px!important;font-weight:750!important}
.st-key-pagination_bar .stButton>button[kind="secondary"]{background:#fff!important;border:1px solid #DCE2EC!important;color:#374151!important}
.st-key-pagination_bar .stButton>button[kind="secondary"]:hover{border-color:#2563EB!important;color:#2563EB!important}

.site-footer{margin-top:18px;margin-bottom:12px;padding:15px 18px;background:#fff;border:1px solid #E2E8F0;border-radius:14px;text-align:center;color:var(--sub);font-size:12.5px;font-weight:600;line-height:1.6;word-break:keep-all}
.site-footer-sub{display:block;margin-top:4px;font-size:11.5px;font-weight:500;color:var(--muted)}

.metric{background:#fff;border:1px solid #E2E8F0;border-radius:14px;padding:14px;min-height:90px}
.metric-label{color:var(--muted);font-size:12px;font-weight:700}
.metric-value{color:var(--brand);font-size:24px;font-weight:850;margin-top:4px}
.status-row{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid #EDF1F6;font-size:13px}
.status-row:last-child{border-bottom:0}
.error-box{background:#FEF2F2;color:#991B1B;padding:10px;border-radius:10px;font-size:12px;margin:6px 0;word-break:break-word}

@media(max-width:900px) and (min-width:641px){
  .st-key-product_grid [data-testid="stHorizontalBlock"]{flex-wrap:wrap!important}
  .st-key-product_grid [data-testid="stColumn"],.st-key-product_grid [data-testid="column"]{flex:0 0 calc(50% - 8px)!important;width:calc(50% - 8px)!important;min-width:calc(50% - 8px)!important}
}
@media(max-width:640px){
  .block-container{padding:.75rem .75rem 3rem!important;width:100%!important;max-width:100%!important}
  .top-nav{margin-bottom:9px}.top-sub{display:none!important}
  .hero-banner{padding:15px 14px;margin-bottom:10px}.hero-headline{font-size:17.5px}
  .hero-stats{flex-wrap:nowrap!important;gap:4px!important;margin-top:9px!important;overflow-x:auto!important}
  .stat-pill{padding:4px 8px!important;font-size:11px!important;gap:4px!important;letter-spacing:-.02em!important;flex-shrink:0!important}
  .st-key-filter_bar [data-testid="stHorizontalBlock"]{
    display:grid!important;
    grid-template-columns:3fr 1fr!important;
    gap:6px!important;
    width:100%!important;
    margin:0!important;
  }
  .st-key-filter_bar [data-testid="stColumn"],
  .st-key-filter_bar [data-testid="column"]{width:100%!important;min-width:0!important}
  div[data-testid="stSelectbox"] div[data-baseweb="select"] > div:first-child{padding-left:9px!important;padding-right:4px!important}
  .st-key-result_bar [data-testid="stHorizontalBlock"]{display:flex!important;flex-direction:row!important;flex-wrap:nowrap!important;justify-content:space-between!important;align-items:center!important;width:100%!important}
  .st-key-result_bar [data-testid="stColumn"],
  .st-key-result_bar [data-testid="column"]{flex:0 1 auto!important;width:auto!important;min-width:0!important}
  .st-key-self_buy_toggle button{height:32px!important;min-height:32px!important;padding:0 11px!important;font-size:12.5px!important}
  .st-key-product_grid [data-testid="stHorizontalBlock"],
  .st-key-related_grid [data-testid="stHorizontalBlock"]{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:12px!important;width:100%!important;margin:0 0 12px 0!important}
  .st-key-product_grid [data-testid="stColumn"],
  .st-key-product_grid [data-testid="column"],
  .st-key-related_grid [data-testid="stColumn"],
  .st-key-related_grid [data-testid="column"]{width:100%!important;min-width:0!important;max-width:100%!important;flex:none!important;margin:0!important;padding:0!important}
  .detail-hero-card{padding:15px 14px}
  .detail-title{font-size:19.5px}
  .pros-cons-grid{grid-template-columns:minmax(0,1fr)!important}
  .creator-review-card{flex-direction:column;gap:10px}
  .creator-thumb-box{width:100%}
  .danawa-benefit{white-space:normal}
  .st-key-pagination_bar [data-testid="stHorizontalBlock"]{gap:4px!important}
  .st-key-pagination_bar [data-testid="stColumn"],.st-key-pagination_bar [data-testid="column"]{min-width:34px!important}
  .st-key-pagination_bar .stButton>button{min-width:34px!important;min-height:36px!important;padding:0 8px!important;font-size:12.5px!important}
  .site-footer{padding:13px 12px;font-size:12px}.site-footer-sub{font-size:11px}
}
</style>
""", unsafe_allow_html=True)
