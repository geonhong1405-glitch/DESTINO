import os
from openai import OpenAI
from dotenv import load_dotenv

# .env 파일을 현재 디렉토리에서 명시적으로 로드
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path=env_path)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def ask_ai_about_attractions(question, attractions, flight_info=None):
    # attractions: list of dicts from Geoapify/Google Places
    context = "\n".join([
        f"상호명: {a.get('name', 'Unknown')}\n주소: {a.get('address', {}).get('formatted', '')}\n카테고리: {', '.join(a.get('categories', []))}\n웹사이트: {a.get('website', '없음')}\n영업시간: {a.get('opening_hours', '정보 없음')}\n" for a in attractions
    ])
    flight_context = ""
    if flight_info:
        flight_context = "\n\n항공권 정보:\n" + "\n".join([
            f"항공사: {f.get('airline', 'Unknown')}, 항공편: {f.get('flight_number', 'Unknown')}, 출발: {f.get('departure', '')}, 도착: {f.get('arrival', '')}, 출발지: {f.get('origin', '')}, 도착지: {f.get('destination', '')}" for f in flight_info
        ])
    prompt = (
        f"관광객이 '{question}'이라고 물어봤을 때, 아래 명소와 항공권 정보 중에서 가장 적합한 정보를 정확하게 추천해줘. "
        f"명소 목록:\n{context}{flight_context}"
    )
    response = client.chat.completions.create(
        model="gpt-4-mini",
        messages=[{"role": "system", "content": "너는 여행지 추천 전문가야."},
                  {"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content
