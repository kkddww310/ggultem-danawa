# 설치 후 첫 실행

1. 저장소 루트에 `collector` 폴더와 `.github/workflows/collect.yml`을 업로드합니다.
2. 기존 `requirements.txt`를 이 폴더의 파일로 교체합니다.
3. GitHub 저장소의 Actions 탭을 엽니다.
4. `Collect YouTube channels and videos`를 선택합니다.
5. `Run workflow`를 눌러 수동 테스트합니다.
6. 성공 후 Supabase의 channels와 videos 테이블에서 행이 생성됐는지 확인합니다.

현재 1차 버전은 채널 발견, 구독자 100만 필터, 최근 영상 동기화, 상품 영상 후보 점수화까지 수행합니다.
OpenRouter 상품 추출 및 새 Streamlit 홈 화면 연결은 이 테스트가 성공한 다음 단계입니다.
