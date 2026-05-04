from supabase import create_client, Client
from app.core.config import settings

url: str = settings.SUPABASE_URL
# service role key bypasses RLS — use for all server-side writes
key: str = settings.SUPABASE_SERVICE_KEY or settings.SUPABASE_KEY
supabase: Client = create_client(url, key)

def get_data(table_name):
    """Supabase에서 데이터 가져오기"""
    try:
        response = supabase.table(table_name).select("*").execute()
        print(f"{table_name}에서 데이터를 성공적으로 가져왔습니다!")
        return response.data
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None