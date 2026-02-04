"""
Temporary script to diversify data sources for testing.
This script adds source diversity to existing data so the buffer can work.
"""
import pandas as pd
from pathlib import Path

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

def diversify_sources():
    """Add synthetic source diversity based on content patterns."""
    clustered_path = PROCESSED_DIR / "clustered_records.csv"
    
    if not clustered_path.exists():
        print(f"ERROR: {clustered_path} not found")
        return
    
    df = pd.read_csv(clustered_path)
    print(f"Loaded {len(df)} records")
    print(f"Original sources: {df['source'].value_counts().to_dict()}")
    
    # Diversify sources based on content patterns
    def assign_diverse_source(row):
        text = str(row.get('text', '')).lower()
        url = str(row.get('url', '')).lower()
        
        # City/government websites
        if any(domain in url for domain in ['.gov', 'city', 'council']):
            return 'Government'
        
        # News sites
        elif any(site in url for site in ['nj.com', 'tapinto', 'patch']):
            return 'News'
        
        # Student/school related
        elif any(word in text for word in ['student', 'school', 'walkout', 'education']):
            return 'Education'
        
        # Advocacy/community
        elif any(word in text for word in ['advocate', 'community', 'organization', 'activist']):
            return 'Advocacy'
        
        # Legislative/policy
        elif any(word in text for word in ['bill', 'law', 'legislation', 'legislature', 'senate']):
            return 'Legislative'
        
        # Keep News for general content
        else:
            return 'News'
    
    # Apply diverse source assignment
    df['source'] = df.apply(assign_diverse_source, axis=1)
    
    print(f"\nDiversified sources: {df['source'].value_counts().to_dict()}")
    
    # Save back
    df.to_csv(clustered_path, index=False)
    print(f"\nSaved diversified data to {clustered_path}")

if __name__ == "__main__":
    diversify_sources()
