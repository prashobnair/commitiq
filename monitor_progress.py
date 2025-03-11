import os
import psycopg2
import time
from dotenv import load_dotenv

def get_progress():
    # Load environment variables
    load_dotenv()

    # Connect to the database
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )

    # Create a cursor
    cur = conn.cursor()

    # Get user count
    cur.execute('SELECT COUNT(*) FROM users_metrics')
    user_count = cur.fetchone()[0]

    # Get repository count
    cur.execute('SELECT COUNT(*) FROM users_repositories')
    repo_count = cur.fetchone()[0]

    # Get repositories with impact scores
    cur.execute('SELECT COUNT(*) FROM users_repositories WHERE technical_impact > 0')
    tech_impact_repos = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM users_repositories WHERE ecosystem_impact > 0')
    eco_impact_repos = cur.fetchone()[0]
    
    cur.execute('SELECT COUNT(*) FROM users_repositories WHERE total_impact > 0')
    total_impact_repos = cur.fetchone()[0]

    # Get average impact scores
    cur.execute('SELECT AVG(technical_impact) FROM users_repositories WHERE technical_impact > 0')
    avg_tech_impact = cur.fetchone()[0] or 0
    
    cur.execute('SELECT AVG(ecosystem_impact) FROM users_repositories WHERE ecosystem_impact > 0')
    avg_eco_impact = cur.fetchone()[0] or 0
    
    cur.execute('SELECT AVG(total_impact) FROM users_repositories WHERE total_impact > 0')
    avg_total_impact = cur.fetchone()[0] or 0

    # Close the connection
    conn.close()

    return {
        'user_count': user_count,
        'repo_count': repo_count,
        'tech_impact_repos': tech_impact_repos,
        'eco_impact_repos': eco_impact_repos,
        'total_impact_repos': total_impact_repos,
        'avg_tech_impact': avg_tech_impact,
        'avg_eco_impact': avg_eco_impact,
        'avg_total_impact': avg_total_impact
    }

def print_progress(progress):
    print("\n" + "=" * 50)
    print(f"Collection Progress - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    print(f"Users collected: {progress['user_count']}/10000 ({progress['user_count']/100:.1f}%)")
    print(f"Repositories collected: {progress['repo_count']}")
    print(f"Repositories per user: {progress['repo_count']/progress['user_count']:.2f}")
    print("\nImpact Scores:")
    print(f"Repositories with technical impact: {progress['tech_impact_repos']} ({progress['tech_impact_repos']/progress['repo_count']*100:.1f}%)")
    print(f"Repositories with ecosystem impact: {progress['eco_impact_repos']} ({progress['eco_impact_repos']/progress['repo_count']*100:.1f}%)")
    print(f"Repositories with total impact: {progress['total_impact_repos']} ({progress['total_impact_repos']/progress['repo_count']*100:.1f}%)")
    print("\nAverage Impact Scores:")
    print(f"Average technical impact: {progress['avg_tech_impact']:.2f}")
    print(f"Average ecosystem impact: {progress['avg_eco_impact']:.2f}")
    print(f"Average total impact: {progress['avg_total_impact']:.2f}")
    print("=" * 50)

if __name__ == "__main__":
    progress = get_progress()
    print_progress(progress) 