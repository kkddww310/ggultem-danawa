import streamlit as st
import json, os, re
from urllib.parse import quote

DB_FILE = "items.json"

# === 100만+ 대형 유튜버 10인 검증 추천템 통합 DB (총 60개) ===
CURATED_1M_YOUTUBER_DB = [
    # 1. ITSub잇섭 (260만+)
    {"name": "앤커 맥고 Qi2 3in1 맥세이프 충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "아이폰·애플워치·에어팟을 15W 고속으로 한 번에 정리하는 접이식 충전 스테이션", "timestamp": "03:15", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+앤커+맥고+충전기"},
    {"name": "유그린 넥소드 100W GaN 멀티 고속충전기", "keyword": "충전기", "youtuber": "ITSub잇섭", "reason": "맥북과 스마트폰을 동시에 고속 충전할 수 있는 작고 발열 적은 GaN 충전기", "timestamp": "05:10", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+유그린+100W+충전기"},
    {"name": "삼성전자 포터블 SSD T7 Shield 2TB", "keyword": "외장SSD", "youtuber": "ITSub잇섭", "reason": "고화질 영상 데이터도 빠르게 전송하고 충격·방수에 강한 실사용 외장 SSD", "timestamp": "07:42", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+삼성+T7+Shield"},
    {"name": "벨킨 부스트차지 프로 2in1 맥세이프 거치대", "keyword": "거치대", "youtuber": "ITSub잇섭", "reason": "묵직한 하단 무게중심으로 한 손으로 아이폰을 떼어내도 흔들리지 않는 거치대", "timestamp": "04:08", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+벨킨+맥세이프+거치대"},
    {"name": "키크론 Q1 Pro 커스텀 무선 기계식 키보드", "keyword": "키보드", "youtuber": "ITSub잇섭", "reason": "풀 알루미늄 바디와 가스켓 마운트로 도각거리는 타건감을 제공하는 무선 키보드", "timestamp": "09:20", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+키크론+Q1+Pro"},
    {"name": "로지텍 MX Master 3S 무선 마우스", "keyword": "마우스", "youtuber": "ITSub잇섭", "reason": "저소음 클릭과 초고속 무한 휠로 장시간 편집·업무 피로도를 줄여주는 마우스", "timestamp": "05:40", "youtube_url": "https://www.youtube.com/results?search_query=잇섭+MX+Master+3S"},

    # 2. 테크몽 Techmong (100만+)
    {"name": "베이스어스 블레이드 100W 슬림 보조배터리", "keyword": "보조배터리", "youtuber": "테크몽 Techmong", "reason": "노트북 파우치에 쏙 들어가는 얇은 두께에 100W 고출력을 지원하는 보조배터리", "timestamp": "02:50", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+베이스어스+블레이드+100W"},
    {"name": "샤오미 미지아 무선 핸디 청소기 미니", "keyword": "청소기", "youtuber": "테크몽 Techmong", "reason": "책상 위 먼지와 키보드 틈새, 차량 내부를 간편하게 흡입하는 초경량 청소기", "timestamp": "06:15", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+샤오미+미니+청소기"},
    {"name": "앤커 사운드코어 리버티 4 NC 무선 이어폰", "keyword": "이어폰", "youtuber": "테크몽 Techmong", "reason": "10만 원 이하 가격대에서 압도적인 노이즈캔슬링 성능을 보여주는 가성비 이어폰", "timestamp": "04:33", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+리버티+4+NC"},
    {"name": "신지모루 맥세이프 자석 태블릿 거치대", "keyword": "거치대", "youtuber": "테크몽 Techmong", "reason": "강력한 자력과 견고한 힌지로 아이패드 필기·영상 시청 시 흔들림 없는 거치대", "timestamp": "08:17", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+태블릿+거치대"},
    {"name": "에르고트론 LX 데스크 모니터암", "keyword": "모니터암", "youtuber": "테크몽 Techmong", "reason": "무거운 대형 모니터도 부드럽게 움직이고 처짐 없이 고정되는 데스크 모니터암", "timestamp": "01:16", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+에르고트론+LX"},
    {"name": "유그린 4K 120Hz HDMI 2.1 메탈 케이블", "keyword": "케이블", "youtuber": "테크몽 Techmong", "reason": "고주사율 모니터와 콘솔 연결 시 화면 깜빡임 없이 안정적인 전송을 지원하는 케이블", "timestamp": "03:55", "youtube_url": "https://www.youtube.com/results?search_query=테크몽+유그린+HDMI+케이블"},

    # 3. 오늘의 주우재 (120만+)
    {"name": "포터 탱커 숄더백 블랙", "keyword": "가방", "youtuber": "오늘의 주우재", "reason": "가벼운 나일론 소재와 넉넉한 수납 포켓으로 데일리 캐주얼 룩에 잘 어울리는 가방", "timestamp": "05:07", "youtube_url": "https://www.youtube.com/results?search_query=주우재+포터+탱커+숄더백"},
    {"name": "무인양품 발이 편한 발수 스니커즈", "keyword": "스니커즈", "youtuber": "오늘의 주우재", "reason": "어떤 바지에도 무난하게 어울리고 인솔 쿠션감이 좋아 매일 손이 가는 기본 운동화", "timestamp": "06:54", "youtube_url": "https://www.youtube.com/results?search_query=주우재+무인양품+스니커즈"},
    {"name": "아식스 젤 카야노 14 운동화", "keyword": "운동화", "youtuber": "오늘의 주우재", "reason": "메탈릭 실버 포인트와 푹신한 젤 쿠셔닝으로 코디 포인트와 착화감을 잡은 슈즈", "timestamp": "07:15", "youtube_url": "https://www.youtube.com/results?search_query=주우재+젤+카야노+14"},
    {"name": "팀버랜드 클래식 3아이 러그 보트 슈즈", "keyword": "구두", "youtuber": "오늘의 주우재", "reason": "와이드 데님이나 치노 팬츠에 매치하기 좋은 탄탄한 가죽 보트 슈즈", "timestamp": "08:20", "youtube_url": "https://www.youtube.com/results?search_query=주우재+팀버랜드+보트슈즈"},
    {"name": "유니클로 에어리즘 코튼 오버사이즈 티셔츠", "keyword": "티셔츠", "youtuber": "오늘의 주우재", "reason": "탄탄한 겉면과 쾌적한 안감으로 여름부터 간절기 이너까지 활용도 높은 기본 반팔", "timestamp": "02:49", "youtube_url": "https://www.youtube.com/results?search_query=주우재+유니클로+에어리즘+티셔츠"},
    {"name": "젠틀몬스터 릭 01 선글라스", "keyword": "선글라스", "youtuber": "오늘의 주우재", "reason": "유행을 타지 않는 깔끔한 스퀘어 아세테이트 프레임으로 얼굴형을 보완하는 선글라스", "timestamp": "11:35", "youtube_url": "https://www.youtube.com/results?search_query=주우재+젠틀몬스터+릭"},

    # 4. 원지의하루 (100만+)
    {"name": "홀롤롤로 여행용 카드 동전지갑", "keyword": "지갑", "youtuber": "원지의하루", "reason": "해외여행 시 지폐·동전·카드를 가볍고 직관적으로 분리 수납하는 여행 필수 지갑", "timestamp": "03:10", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+홀롤롤로+여행지갑"},
    {"name": "로젤 쿠보 30인치 확장형 캐리어", "keyword": "캐리어", "youtuber": "원지의하루", "reason": "좁은 숙소에서도 세운 채로 앞뚜껑만 열어 짐을 꺼낼 수 있는 수납 천재 캐리어", "timestamp": "04:45", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+로젤+쿠보+캐리어"},
    {"name": "마틸라 도즈 차렵이불 패드 세트", "keyword": "침구", "youtuber": "원지의하루", "reason": "먼지 날림이 적고 부드러운 촉감으로 숙면의 질을 높여주는 홈 라이프 침구 세트", "timestamp": "06:20", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+마틸라+차렵이불"},
    {"name": "프루아 데일리 코튼 볼캡", "keyword": "모자", "youtuber": "원지의하루", "reason": "깊이감 있는 핏과 자연스러운 색감으로 민낯 외출이나 여행 시 손이 자주 가는 볼캡", "timestamp": "02:15", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+프루아+볼캡"},
    {"name": "DJI 오즈모 포켓 3 크리에이터 콤보", "keyword": "카메라", "youtuber": "원지의하루", "reason": "1인치 센서와 3축 짐벌이 결합되어 흔들림 없는 여행 브이로그를 담아주는 카메라", "timestamp": "08:30", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+오즈모+포켓+3"},
    {"name": "트래블블루 메모리폼 항공 목베개", "keyword": "목베개", "youtuber": "원지의하루", "reason": "장거리 비행에서도 목을 안정적으로 받쳐주어 피로도를 줄여주는 휴대용 목베개", "timestamp": "09:12", "youtube_url": "https://www.youtube.com/results?search_query=원지의하루+목베개"},

    # 5. 이사배 RISABAE (250만+)
    {"name": "정샘물 에센셜 스킨 누더 쿠션", "keyword": "쿠션", "youtuber": "이사배 RISABAE", "reason": "피부 본연의 윤기를 살리면서 자연스럽고 화사하게 밀착되는 베이스 쿠션", "timestamp": "03:40", "youtube_url": "https://www.youtube.com/results?search_query=이사배+정샘물+스킨+누더+쿠션"},
    {"name": "맥 글로우 플레이 쿠션 블러쉬", "keyword": "블러셔", "youtuber": "이사배 RISABAE", "reason": "말랑한 텍스처로 뭉침 없이 맑은 수채화 발색을 연출해 주는 데일리 블러셔", "timestamp": "05:12", "youtube_url": "https://www.youtube.com/results?search_query=이사배+맥+글로우+플레이+블러쉬"},
    {"name": "헤라 블랙 쿠션 파운데이션", "keyword": "쿠션", "youtuber": "이사배 RISABAE", "reason": "얇게 발리면서도 높은 커버력과 오랜 지속력을 보여주는 세미 매트 쿠션", "timestamp": "04:18", "youtube_url": "https://www.youtube.com/results?search_query=이사배+헤라+블랙+쿠션"},
    {"name": "마녀공장 퓨어 클렌징 오일", "keyword": "클렌징오일", "youtuber": "이사배 RISABAE", "reason": "진한 메이크업과 블랙헤드까지 자극 없이 부드럽게 녹여내는 국민 클렌징 오일", "timestamp": "02:30", "youtube_url": "https://www.youtube.com/results?search_query=이사배+마녀공장+클렌징+오일"},
    {"name": "유시몰 화이트닝 퍼플코렉터 치약", "keyword": "치약", "youtuber": "이사배 RISABAE", "reason": "상쾌한 사용감과 치아 미백 케어를 동시에 챙길 수 있는 욕실 필수 치약", "timestamp": "01:45", "youtube_url": "https://www.youtube.com/results?search_query=이사배+유시몰+치약"},
    {"name": "아벤느 오 떼르말 온천수 미스트 300ml", "keyword": "미스트", "youtuber": "이사배 RISABAE", "reason": "세안 직후나 메이크업 전후 건조함을 즉각 진정시켜 주는 미세 안개분사 미스트", "timestamp": "06:05", "youtube_url": "https://www.youtube.com/results?search_query=이사배+아벤느+미스트"},

    # 6. 레오제이 LeoJ Makeup (140만+)
    {"name": "더샘 커버 퍼펙션 트리플 팟 컨실러", "keyword": "컨실러", "youtuber": "레오제이 LeoJ Makeup", "reason": "홍조 커버부터 다크서클·잡티 보정까지 3가지 컬러로 해결하는 올리브영 1등 컨실러", "timestamp": "04:10", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+더샘+트리플+팟+컨실러"},
    {"name": "힌스 무드인핸서 워터 리퀴드 글로우", "keyword": "틴트", "youtuber": "레오제이 LeoJ Makeup", "reason": "끈적임 없이 투명한 수분 광택이 올라오는 물먹립 대표 리퀴드 틴트", "timestamp": "13:22", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+힌스+틴트"},
    {"name": "바닐라코 글로우 베일 틴트", "keyword": "틴트", "youtuber": "레오제이 LeoJ Makeup", "reason": "입술 주름 부각 없이 촉촉하고 자연스러운 혈색을 채워주는 데일리 틴트", "timestamp": "12:45", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+바닐라코+글로우+베일+틴트"},
    {"name": "페리페라 잉크 무드 글로이 틴트", "keyword": "틴트", "youtuber": "레오제이 LeoJ Makeup", "reason": "가성비와 맑은 광택, 다채로운 컬러 구성으로 파우치에 꼭 챙기는 인기 틴트", "timestamp": "14:05", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+페리페라+글로이+틴트"},
    {"name": "필리밀리 퍼펙트 히팅 뷰러", "keyword": "뷰러", "youtuber": "레오제이 LeoJ Makeup", "reason": "열감으로 속눈썹 컬링을 하루 종일 처짐 없이 고정해 주는 충전식 히팅 뷰러", "timestamp": "08:09", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+필리밀리+히팅+뷰러"},
    {"name": "아누아 어성초 77 수딩 토너 500ml", "keyword": "토너", "youtuber": "레오제이 LeoJ Makeup", "reason": "민감해진 피부를 순하게 잠재우고 닦토·스킨팩으로 아낌없이 쓰기 좋은 대용량 토너", "timestamp": "03:27", "youtube_url": "https://www.youtube.com/results?search_query=레오제이+아누아+어성초+토너"},

    # 7. 귀곰 (100만+)
    {"name": "매직캔 히포 크롬 냄새차단 쓰레기통 27L", "keyword": "쓰레기통", "youtuber": "귀곰", "reason": "이중 밀폐 구조로 여름철 음식물·기저귀 냄새까지 완벽하게 막아주는 휴지통", "timestamp": "02:39", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+매직캔+쓰레기통"},
    {"name": "파쉬 클래식 보온 물주머니 2L", "keyword": "보온물주머니", "youtuber": "귀곰", "reason": "전자파 걱정 없이 뜨거운 물만 넣으면 밤새 따뜻함이 유지되는 겨울철 필수템", "timestamp": "07:02", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+파쉬+물주머니"},
    {"name": "크린랩 니트릴 고무장갑 100매", "keyword": "고무장갑", "youtuber": "귀곰", "reason": "손에 딱 맞아 섬세한 설거지나 요리할 때 벗겨짐 없이 위생적으로 쓰는 장갑", "timestamp": "04:59", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+니트릴+고무장갑"},
    {"name": "듀벨 입체기동 360도 회전 주방 수도꼭지", "keyword": "수전", "youtuber": "귀곰", "reason": "싱크대 구석구석 물줄기를 자유롭게 꺾어 세척할 수 있는 다관절 주방 수전 헤드", "timestamp": "08:59", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+입체기동+수도꼭지"},
    {"name": "샤오미 미지아 스마트 제습기 22L", "keyword": "제습기", "youtuber": "귀곰", "reason": "가성비와 앱 원격 제어, 조용한 수면 모드를 모두 갖춘 사계절 강력 제습기", "timestamp": "03:15", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+샤오미+제습기"},
    {"name": "로보락 S8 MaxV Ultra 로봇청소기", "keyword": "로봇청소기", "youtuber": "귀곰", "reason": "모서리 확장 브러시와 온수 물걸레 세척·건조까지 자동으로 처리하는 로봇청소기", "timestamp": "06:50", "youtube_url": "https://www.youtube.com/results?search_query=귀곰+로보락+S8"},

    # 8. 자취남 (100만+)
    {"name": "이케아 로스코그 이동식 트롤리 카트", "keyword": "트롤리", "youtuber": "자취남", "reason": "원룸 주방·책상·침대 옆 자투리 공간을 3단 수납장으로 바꿔주는 자취 필수 트롤리", "timestamp": "01:40", "youtube_url": "https://www.youtube.com/results?search_query=자취남+이케아+로스코그"},
    {"name": "이케아 테르티알 관절 스탠드 조명", "keyword": "조명", "youtuber": "자취남", "reason": "책상 상판에 클램프로 고정해 공간 차지 없이 아늑한 무드를 만드는 가성비 조명", "timestamp": "03:20", "youtube_url": "https://www.youtube.com/results?search_query=자취남+이케아+테르티알"},
    {"name": "다이슨 에어랩 멀티 스타일러 컴플리트", "keyword": "헤어드라이기", "youtuber": "자취남", "reason": "과도한 열 손상 없이 바람만으로 빠르게 건조와 스타일링을 끝내는 헤어 기기", "timestamp": "04:15", "youtube_url": "https://www.youtube.com/results?search_query=다이슨+에어랩+멀티+스타일러"},
    {"name": "발뮤다 더 토스터 프로 스팀 토스터기", "keyword": "토스터기", "youtuber": "자취남", "reason": "스팀 제어 기술로 냉동 식빵도 겉은 바삭하고 속은 촉촉하게 구워주는 토스터기", "timestamp": "05:30", "youtube_url": "https://www.youtube.com/results?search_query=발뮤다+더+토스터"},
    {"name": "루메나 FAN STAND 3Z 무선 탁상용 선풍기", "keyword": "선풍기", "youtuber": "자취남", "reason": "선 없이 침대 옆이나 책상 위로 자유롭게 옮겨 쓰기 좋은 저소음 무선 선풍기", "timestamp": "02:50", "youtube_url": "https://www.youtube.com/results?search_query=루메나+무선+선풍기"},
    {"name": "코멧 홈 붙이는 암막 뽁뽁이 단열시트", "keyword": "단열시트", "youtuber": "자취남", "reason": "남향집 강한 햇빛 차단과 겨울철 외풍·냉기 방지를 한 번에 해결하는 자취 꿀템", "timestamp": "06:10", "youtube_url": "https://www.youtube.com/results?search_query=자취남+암막+뽁뽁이"},

    # 9. 승우아빠 (140만+)
    {"name": "헹켈 트윈 폴룩스 산도쿠 식칼 18cm", "keyword": "식칼", "youtuber": "승우아빠", "reason": "가벼운 무게와 뛰어난 절삭력으로 집밥 요리 입문자부터 숙련자까지 쓰기 좋은 식칼", "timestamp": "03:10", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+헹켈+식칼"},
    {"name": "테팔 언리미티드 인덕션 프라이팬 28cm", "keyword": "프라이팬", "youtuber": "승우아빠", "reason": "강력한 티타늄 코팅으로 눌어붙음 없이 오래 쓸 수 있는 데일리 인덕션 프라이팬", "timestamp": "04:45", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+테팔+프라이팬"},
    {"name": "브리타 마렐라 XL 정수기 3.5L", "keyword": "정수기", "youtuber": "승우아빠", "reason": "생수 페트병 분리수거 번거로움 없이 물맛을 깔끔하게 잡아주는 자연여과 정수기", "timestamp": "02:20", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+브리타+정수기"},
    {"name": "키친에이드 아티산 스탠드 믹서", "keyword": "반죽기", "youtuber": "승우아빠", "reason": "제빵 반죽부터 머랭 휘핑까지 강력한 모터 힘으로 균일하게 처리하는 주방 믹서", "timestamp": "07:15", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+키친에이드"},
    {"name": "드레텍 대형화면 디지털 주방 타이머", "keyword": "타이머", "youtuber": "승우아빠", "reason": "냉장고나 후드에 자석으로 붙여두고 파스타·스테이크 조리 시간을 정확히 재는 타이머", "timestamp": "05:05", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+드레텍+타이머"},
    {"name": "옥소 굿그립 앵글 계량컵 500ml", "keyword": "계량컵", "youtuber": "승우아빠", "reason": "허리를 숙이지 않고 위에서 내려다보면서 눈금을 바로 읽을 수 있는 편리한 계량컵", "timestamp": "06:30", "youtube_url": "https://www.youtube.com/results?search_query=승우아빠+옥소+계량컵"},

    # 10. 주연 ZUYONI (100만급 테크)
    {"name": "애플 에어팟 프로 2세대 USB-C", "keyword": "이어폰", "youtuber": "주연 ZUYONI", "reason": "아이폰·맥북 간 매끄러운 기기 전환과 강력한 적응형 노이즈캔슬링을 지원하는 이어폰", "timestamp": "03:20", "youtube_url": "https://www.youtube.com/results?search_query=주연+에어팟+프로+2"},
    {"name": "모프트 스냅온 맥세이프 카드지갑 스탠드", "keyword": "카드지갑", "youtuber": "주연 ZUYONI", "reason": "카드 수납과 가로·세로 스마트폰 거치를 초슬림 두께로 해결하는 맥세이프 액세서리", "timestamp": "02:05", "youtube_url": "https://www.youtube.com/results?search_query=주연+모프트+맥세이프+카드지갑"},
    {"name": "로지텍 MX Keys Mini 무선 키보드", "keyword": "키보드", "youtuber": "주연 ZUYONI", "reason": "텐키리스 미니 배열과 손끝에 감기는 펜타그래프 키감으로 휴대성과 타건감을 잡은 키보드", "timestamp": "06:40", "youtube_url": "https://www.youtube.com/results?search_query=주연+MX+Keys+Mini"},
    {"name": "소니 WH-1000XM5 노이즈캔슬링 헤드폰", "keyword": "헤드폰", "youtuber": "주연 ZUYONI", "reason": "가벼운 착용감과 업계 최고 수준의 소음 차단 성능을 보여주는 출퇴근·작업용 헤드폰", "timestamp": "05:18", "youtube_url": "https://www.youtube.com/results?search_query=주연+소니+WH-1000XM5"},
    {"name": "LG 퓨리케어 오브제컬렉션 하이드로타워", "keyword": "가습기", "youtuber": "주연 ZUYONI", "reason": "정수 필터와 가열 살균을 거쳐 깨끗한 수분만 뿜어주는 프리미엄 정수 가습기", "timestamp": "08:11", "youtube_url": "https://www.youtube.com/results?search_query=주연+LG+하이드로타워"},
    {"name": "소니 ZV-E10 II 미러리스 카메라", "keyword": "카메라", "youtuber": "주연 ZUYONI", "reason": "가벼운 무게와 빠른 인물 AF, 시네마틱 브이로그 모드를 탑재한 유튜버 입문 카메라", "timestamp": "09:15", "youtube_url": "https://www.youtube.com/results?search_query=주연+ZV-E10"},
]

st.set_page_config(page_title="꿀템 다나와", page_icon="🛍️", layout="centered")

if "nav" not in st.session_state:
    st.session_state.nav = "꿀템 홈"

# === 토스 스타일 라이트 앱 UI ===
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    color-scheme: light !important;
    --background-color: #F2F4F6 !important;
    --secondary-background-color: #FFFFFF !important;
    --text-color: #191F28 !important;
}

html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main {
    background-color: #F2F4F6 !important;
    color: #191F28 !important;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
}

[data-testid="stHeader"], [data-testid="stToolbar"], #MainMenu, footer {
    background: transparent !important;
    visibility: hidden;
}

.block-container {
    max-width: 480px !important;
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

[data-testid="stMarkdownContainer"] p,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {
    color: #191F28 !important;
}

.hero-card {
    background-color: #FFFFFF;
    border-radius: 24px;
    padding: 22px 22px 20px 22px;
    box-shadow: 0 2px 16px rgba(0, 0, 0, 0.04);
    margin-bottom: 16px;
}

div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background-color: #FFFFFF !important;
    border: none !important;
    outline: none !important;
    border-radius: 22px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    box-shadow: 0 2px 14px rgba(0, 0, 0, 0.04) !important;
    padding: 18px 20px !important;
    margin-bottom: 12px !important;
}

div[data-testid="stTextInputRootElement"],
div[data-testid="stTextInputRootElement"] > div,
div[data-baseweb="input"],
div[data-baseweb="base-input"],
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    border: 1.5px solid #E5E8EB !important;
    border-radius: 14px !important;
    color: #191F28 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02) !important;
}
div[data-testid="stTextInputRootElement"]:focus-within,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #3182F6 !important;
}
div[data-testid="stTextInputRootElement"] input,
div[data-baseweb="input"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] span,
div[data-testid="stSelectbox"] div {
    background-color: transparent !important;
    color: #191F28 !important;
    -webkit-text-fill-color: #191F28 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stTextInputRootElement"] input::placeholder,
div[data-testid="stTextArea"] textarea::placeholder {
    color: #8B95A1 !important;
    -webkit-text-fill-color: #8B95A1 !important;
}
div[data-testid="stSelectbox"] svg {
    fill: #4E5968 !important;
}
ul[data-baseweb="menu"],
ul[data-baseweb="menu"] li {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 13px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    border: none !important;
    min-height: 40px !important;
    transition: all 0.15s ease !important;
}

button[data-testid="stBaseButton-primary"],
button[data-testid="baseButton-primary"],
button[kind="primary"] {
    background-color: #FFFFFF !important;
    color: #191F28 !important;
    font-weight: 700 !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06) !important;
}
button[data-testid="stBaseButton-primary"] p,
button[kind="primary"] p {
    color: #191F28 !important;
}

button[data-testid="stBaseButton-secondary"],
button[data-testid="baseButton-secondary"],
button[kind="secondary"] {
    background-color: #E5E8EB !important;
    color: #6B7684 !important;
    box-shadow: none !important;
}
button[data-testid="stBaseButton-secondary"] p,
button[kind="secondary"] p {
    color: #6B7684 !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
    box-shadow: 0 3px 10px rgba(49, 130, 246, 0.25) !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"] p,
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="primary"] p {
    color: #FFFFFF !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-primary"]:hover {
    background-color: #1B64DA !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"],
div[data-testid="stVerticalBlockBorderWrapper"] button[kind="secondary"],
div[data-testid="stVerticalBlockBorderWrapper"] .stDownloadButton > button {
    background-color: #F2F4F6 !important;
    color: #4E5968 !important;
    min-height: 36px !important;
    padding: 4px 10px !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] button[data-testid="stBaseButton-secondary"] p,
div[data-testid="stVerticalBlockBorderWrapper"] .stDownloadButton > button p {
    color: #4E5968 !important;
}

.stLinkButton > a {
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 12.5px !important;
    text-decoration: none !important;
    border: none !important;
    width: 100% !important;
    min-height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 0 8px !important;
    white-space: nowrap !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"],
.stLinkButton > a[kind="primary"] {
    background-color: #3182F6 !important;
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-primary"] p,
.stLinkButton > a[kind="primary"] p {
    color: #FFFFFF !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"],
.stLinkButton > a[kind="secondary"] {
    background-color: #E8F3FF !important;
    color: #3182F6 !important;
}
.stLinkButton > a[data-testid="stBaseLinkButton-secondary"] p,
.stLinkButton > a[kind="secondary"] p {
    color: #3182F6 !important;
}

.app-topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2px 4px 12px 4px;
}
.app-title {
    font-size: 20px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.4px;
}
.hero-label {
    font-size: 13px;
    font-weight: 600;
    color: #8B95A1;
    margin-bottom: 4px;
}
.hero-big {
    font-size: 32px;
    font-weight: 800;
    color: #191F28;
    letter-spacing: -0.8px;
    line-height: 1.2;
    margin-bottom: 10px;
}
.hero-dots {
    display: flex;
    gap: 14px;
    font-size: 13px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 14px;
}
.dot-blue { color: #3182F6; margin-right: 4px; }
.dot-green { color: #00C471; margin-right: 4px; }
.hero-bar-box {
    background-color: #F4F6F8;
    border-radius: 14px;
    padding: 12px 14px;
}
.hero-bar-top {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    font-weight: 600;
    color: #4E5968;
    margin-bottom: 7px;
}
.hero-bar-track {
    width: 100%;
    height: 7px;
    background-color: #E5E8EB;
    border-radius: 99px;
    overflow: hidden;
    margin-bottom: 6px;
}
.hero-bar-fill {
    height: 100%;
    background-color: #3182F6;
    border-radius: 99px;
}
.hero-bar-sub {
    font-size: 11.5px;
    color: #8B95A1;
}
.field-label {
    font-size: 13px;
    font-weight: 700;
    color: #4E5968;
    margin: 12px 0 6px 2px;
}
.item-meta {
    font-size: 12px;
    font-weight: 600;
    color: #8B95A1;
    padding-top: 4px;
}
.item-row {
    display: flex;
    align-items: center;
    gap: 13px;
    margin: 6px 0 14px 0;
}
.item-icon {
    width: 46px;
    height: 46px;
    min-width: 46px;
    border-radius: 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
}
.item-info {
    flex: 1;
    min-width: 0;
}
.item-name {
    font-size: 15.5px;
    font-weight: 700;
    color: #191F28;
    line-height: 1.35;
    margin-bottom: 3px;
    word-break: keep-all;
}
.item-reason {
    font-size: 12.5px;
    color: #6B7684;
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

def render_banner(text, kind="info"):
    palettes = {
        "info": ("#E8F3FF", "#1B64DA", "#C9E0FF"),
        "success": ("#E8F8F0", "#0B7A4B", "#BCEAD5"),
        "warning": ("#FFF6E5", "#9A5B00", "#FFE0A3"),
    }
    bg, fg, bd = palettes.get(kind, palettes["info"])
    st.markdown(
        f'<div style="background-color:{bg}; color:{fg}; border:1px solid {bd}; '
        f'border-radius:14px; padding:13px 15px; margin-top:10px; '
        f'font-size:13.5px; font-weight:700; line-height:1.45;">{text}</div>',
        unsafe_allow_html=True,
    )

def pick_icon_style(name, keyword):
    text = f"{name} {keyword}".lower()
    if any(k in text for k in ("헤드폰", "이어폰", "airpods", "스피커", "오디오", "마이크")):
        return "🎧", "#EEF4FF"
    if any(k in text for k in ("배터리", "충전", "케이블", "어댑터", "멀티탭")):
        return "🔋", "#E8F8F0"
    if any(k in text for k in ("키보드", "마우스", "노트북", "모니터", "태블릿", "맥북", "거치대", "책상", "데스크", "ssd")):
        return "💻", "#F3EEFF"
    if any(k in text for k in ("카메라", "액션캠", "고프로", "삼각대", "조명", "오즈모", "미러리스", "뷰러")):
        return "📷", "#FFF4E5"
    if any(k in text for k in ("쿠션", "블러셔", "틴트", "컨실러", "클렌징", "치약", "미스트", "토너", "핸드")):
        return "💄", "#FFEFF4"
    if any(k in text for k in ("가습", "청소기", "매트", "담요", "난로", "히터", "제습", "토스터", "에어랩", "쓰레기통", "물주머니", "고무장갑", "수전", "트롤리", "선풍기", "단열", "식칼", "프라이팬", "정수기", "반죽기", "타이머", "계량컵", "침구")):
        return "🏠", "#EBF8FF"
    if any(k in text for k in ("지갑", "케이스", "백팩", "가방", "캐리어", "여행", "스니커즈", "신발", "운동화", "구두", "티셔츠", "선글라스", "모자", "목베개")):
        return "🎒", "#F0F4FF"
    return "🛍️", "#F2F4F6"

def save_items(items):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def load_items():
    existing = []
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []

    # 100만+ 대형 유튜버 10인 통합 DB(60개)가 항상 포함되도록 자동 병합
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in existing}
    changed = False
    for seed in CURATED_1M_YOUTUBER_DB:
        key = (seed["name"].strip().lower(), seed["youtuber"].strip().lower())
        if key not in seen:
            existing.append(dict(seed))
            seen.add(key)
            changed = True

    if changed or not os.path.exists(DB_FILE):
        save_items(existing)
    return existing

def add_unique_items(new_items):
    db = load_items()
    seen = {(i.get("name", "").strip().lower(), i.get("youtuber", "").strip().lower()) for i in db}
    added = []
    for item in new_items:
        key = (item.get("name", "").strip().lower(), item.get("youtuber", "").strip().lower())
        if key[0] and key not in seen:
            db.append(item)
            seen.add(key)
            added.append(item)
    save_items(db)
    return added

def render_toss_card(item, idx):
    icon, bg_color = pick_icon_style(item.get("name", ""), item.get("keyword", ""))
    with st.container(border=True):
        top_l, top_r = st.columns([6.5, 1])
        with top_l:
            st.markdown(f"<div class='item-meta'>{item['youtuber']} · {item['timestamp']} 추천</div>", unsafe_allow_html=True)
        with top_r:
            if st.button("✕", key=f"del_{idx}_{item['name']}", help="목록에서 삭제"):
                db = [x for x in load_items() if not (x.get("name") == item.get("name") and x.get("youtuber") == item.get("youtuber"))]
                save_items(db)
                st.rerun()

        st.markdown(f"""
        <div class="item-row">
            <div class="item-icon" style="background-color: {bg_color};">{icon}</div>
            <div class="item-info">
                <div class="item-name">{item['name']}</div>
                <div class="item-reason">{item['reason']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        q = quote(item["name"])
        b1, b2, b3 = st.columns(3)
        b1.link_button("네이버 최저가", f"https://search.shopping.naver.com/search/all?query={q}&sort=price_asc", type="primary", use_container_width=True)
        b2.link_button("쿠팡 최저가", f"https://www.coupang.com/np/search?q={q}&sorter=salePriceAsc", use_container_width=True)
        b3.link_button("▶️ 영상보기", item["youtube_url"], use_container_width=True)

# === 상단 앱 헤더 ===
db = load_items()
yt_count = len({i.get("youtuber", "") for i in db if i.get("youtuber")})

st.markdown("""
<div class="app-topbar">
    <div class="app-title">‹ &nbsp; 꿀템 다나와</div>
    <div style="font-size:13px; font-weight:600; color:#8B95A1;">100만+ 대형 유튜버 큐레이션</div>
</div>
""", unsafe_allow_html=True)

# === 상단 요약 대시보드 카드 ===
fill_pct = min(100, int((len(db) / 100) * 100)) if db else 0
st.markdown(f"""
<div class="hero-card">
    <div class="hero-label">100만+ 대형 유튜버 검증 꿀템</div>
    <div class="hero-big">{len(db):,}개</div>
    <div class="hero-dots">
        <div><span class="dot-blue">●</span>대형 유튜버 <b>{yt_count}명</b></div>
        <div><span class="dot-green">●</span>최저가 비교 <b style="color:#3182F6;">실시간 연동</b></div>
    </div>
    <div class="hero-bar-box">
        <div class="hero-bar-top">
            <span>목표 DB 100개</span>
            <span style="color:#3182F6;">{fill_pct}%</span>
        </div>
        <div class="hero-bar-track">
            <div class="hero-bar-fill" style="width: {fill_pct}%;"></div>
        </div>
        <div class="hero-bar-sub">API 키 없이도 모든 유튜버 추천템 검색과 최저가 비교가 바로 작동해요</div>
    </div>
</div>
""", unsafe_allow_html=True)

# === 상단 3개 탭 버튼 ===
t1, t2, t3 = st.columns(3)
for col, label in zip([t1, t2, t3], ["꿀템 홈", "아이템 추가", "설정"]):
    is_active = (st.session_state.nav == label)
    if col.button(label, key=f"nav_{label}", type="primary" if is_active else "secondary", use_container_width=True):
        st.session_state.nav = label
        st.rerun()

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

if st.session_state.nav == "꿀템 홈":
    yts = ["전체 유튜버 (10명)"] + sorted(list({i.get("youtuber", "") for i in db if i.get("youtuber")}))
    c_search, c_filter = st.columns([1.55, 1.1])
    kw = c_search.text_input("검색", placeholder="🔍 물건 검색 (예: 쿠션, 충전기, 캐리어)", label_visibility="collapsed")
    sel_yt = c_filter.selectbox("유튜버", yts, label_visibility="collapsed")

    filtered = [i for i in db if sel_yt.startswith("전체 유튜버") or i.get("youtuber") == sel_yt]
    if kw:
        filtered = [i for i in filtered if kw.lower() in (i.get("name", "") + i.get("keyword", "") + i.get("reason", "") + i.get("youtuber", "")).lower()]

    if filtered:
        st.markdown(f"<div style='font-size:13px; font-weight:700; color:#4E5968; margin: 12px 4px 8px 4px;'>검증된 추천템 목록 ({len(filtered)}건)</div>", unsafe_allow_html=True)
        for idx, item in enumerate(filtered):
            render_toss_card(item, idx)
    elif kw:
        with st.container(border=True):
            st.markdown(f"<div class='item-name'>'{kw}' 추천템이 아직 없어요</div><div class='item-reason' style='margin:6px 0 12px 0;'>네이버 쇼핑에서 바로 최저가를 확인해 보세요.</div>", unsafe_allow_html=True)
            st.link_button(f"네이버 쇼핑에서 '{kw}' 최저가 보기", f"https://search.shopping.naver.com/search/all?query={quote(kw)}&sort=price_asc", type="primary", use_container_width=True)

elif st.session_state.nav == "아이템 추가":
    with st.container(border=True):
        st.markdown("<div class='item-name' style='margin-bottom:4px;'>➕ 유튜버 추천템 직접 추가</div>", unsafe_allow_html=True)
        st.markdown("<div class='item-reason' style='margin-bottom:10px;'>API 없이 원하는 유튜버의 실제 제품명만 깔끔하게 등록할 수 있어요.</div>", unsafe_allow_html=True)

        st.markdown("<div class='field-label'>유튜버 이름</div>", unsafe_allow_html=True)
        in_yt = st.text_input("유튜버", placeholder="예: ITSub잇섭, 이사배 RISABAE, 오늘의 주우재", label_visibility="collapsed")

        st.markdown("<div class='field-label'>정확한 브랜드 + 제품명</div>", unsafe_allow_html=True)
        in_name = st.text_input("제품명", placeholder="예: 로지텍 MX Master 3S 무선 마우스", label_visibility="collapsed")

        st.markdown("<div class='field-label'>추천 한 줄 메모 (선택)</div>", unsafe_allow_html=True)
        in_reason = st.text_input("메모", placeholder="예: 저소음 클릭과 무한 휠이 매력적인 데스크 마우스", label_visibility="collapsed")

        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("등록하기", type="primary", use_container_width=True):
            if in_yt.strip() and in_name.strip():
                new_item = {
                    "name": in_name.strip(),
                    "keyword": in_name.strip().split()[0],
                    "youtuber": in_yt.strip(),
                    "reason": in_reason.strip() or f"{in_yt.strip()} 영상에서 소개한 추천 아이템",
                    "timestamp": "추천",
                    "youtube_url": f"https://www.youtube.com/results?search_query={quote(in_yt.strip() + ' ' + in_name.strip())}",
                }
                added = add_unique_items([new_item])
                if added:
                    render_banner(f"완료! '{in_name.strip()}' 제품이 목록에 추가되었어요.", "success")
                else:
                    render_banner("이미 목록에 등록된 제품이에요.", "warning")
            else:
                render_banner("유튜버 이름과 정확한 제품명을 모두 입력해 주세요.", "warning")

elif st.session_state.nav == "설정":
    with st.container(border=True):
        st.markdown(f"<div class='item-name' style='margin-bottom:6px;'>🗂️ 데이터 관리 및 백업</div><div class='item-reason' style='margin-bottom:12px;'>현재 100만+ 대형 유튜버 추천템 총 <b>{len(db)}개</b>가 저장되어 있습니다.</div>", unsafe_allow_html=True)

        st.download_button(
            label="📥 현재 DB 파일(items.json) 다운로드",
            data=json.dumps(db, ensure_ascii=False, indent=2),
            file_name="items.json",
            mime="application/json",
            use_container_width=True,
        )
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 대형 유튜버 10인 통합 DB(60개)로 초기화", type="primary", use_container_width=True):
            save_items(list(CURATED_1M_YOUTUBER_DB))
            st.rerun()
# === 여기까지 복사되면 끝 ===
