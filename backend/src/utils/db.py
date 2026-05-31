from sqlalchemy import create_engine, text

DATABASE_URL = 'postgresql://postgres:password@localhost:5433/customer_intelligence'

print(f"[db] Connecting to: {DATABASE_URL}")

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

def test_connection():
    with engine.connect() as conn:
        result = conn.execute(text('SELECT version()'))
        print(f'PostgreSQL connected: {result.fetchone()[0]}')

if __name__ == '__main__':
    test_connection()