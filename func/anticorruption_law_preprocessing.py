# -*- coding: utf-8 -*-
import json
import pandas as pd
import glob
import re
from datetime import datetime

def process_anticorruption_law_data():
    """
    Process JSON files with anticorruption_law_ prefix and save to Excel file
    """
    # JSON file path pattern
    json_pattern = "/home/son/SKN12-FINAL-AIRFLOW/crawler_result/anticorruption_law_*.json"
    json_files = glob.glob(json_pattern)
    
    if not json_files:
        print("No JSON files with anticorruption_law_ prefix found.")
        return
    
    all_data = []
    
    for json_file in json_files:
        print(f"Processing: {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract required fields
        law_name = data.get('법명', '')
        law_info = data.get('시행_법률_정보', '')
        source_url = data.get('소스_URL', '')
        pgroup_texts = data.get('pgroup_텍스트', [])
        
        # Process pgroup_texts
        processed_articles = process_pgroup_texts(pgroup_texts)
        
        # Create rows for each article
        for article_data in processed_articles:
            row = {
                '법명': law_name,
                '법률정보': law_info,
                '조문': article_data['조문'],
                '내용': article_data['내용'],
                '소스_URL': source_url
            }
            all_data.append(row)
    
    # Create DataFrame
    df = pd.DataFrame(all_data)
    
    # Save to Excel file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"/home/son/SKN12-FINAL-AIRFLOW/crawler_result/anticorruption_law_processed_{timestamp}.xlsx"
    df.to_excel(output_path, index=False, engine='openpyxl')
    
    print(f"Processing completed: {output_path}")
    print(f"Total {len(df)} articles processed.")
    
    return output_path

def process_pgroup_texts(pgroup_texts):
    """
    Process pgroup_texts list to separate articles and content
    """
    processed_data = []
    current_chapter = ""
    
    # Define patterns for chapters and articles
    chapter_pattern = r'^제(\d+)장\s*(.*)'
    article_pattern = r'^제(\d+)조\(([^)]+)\)'
    
    for text in pgroup_texts:
        text = text.strip()
        
        # Check for chapter pattern
        chapter_match = re.match(chapter_pattern, text)
        if chapter_match:
            chapter_num = chapter_match.group(1)
            chapter_title = chapter_match.group(2)
            current_chapter = f"제{chapter_num}장 {chapter_title}".strip()
            continue
        
        # Check for article pattern
        article_match = re.match(article_pattern, text)
        if article_match:
            article_num = article_match.group(1)
            article_title = article_match.group(2)
            
            # Construct article (current chapter + article)
            if current_chapter:
                full_article = f"{current_chapter} 제{article_num}조({article_title})"
            else:
                full_article = f"제{article_num}조({article_title})"
            
            # Extract content (all text after first ')')
            paren_index = text.find(')')
            if paren_index != -1 and paren_index + 1 < len(text):
                content = text[paren_index + 1:].strip()
            else:
                content = ""
            
            processed_data.append({
                '조문': full_article,
                '내용': content
            })
    
    return processed_data

if __name__ == "__main__":
    process_anticorruption_law_data()