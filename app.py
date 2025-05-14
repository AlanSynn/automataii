import sys
import os

# 프로젝트의 'src' 디렉토리를 Python 경로에 추가합니다.
# 이렇게 하면 루트 디렉토리에서 스크립트를 실행해도
# 'automataii' 패키지를 찾을 수 있습니다.
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 이제 패키지에서 main 함수를 가져올 수 있습니다.
from automataii.__main__ import main

if __name__ == "__main__":
    # 애플리케이션의 메인 함수를 실행합니다.
    main()
