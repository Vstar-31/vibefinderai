#!/usr/bin/env python3
"""
VIBEFINDER AI - Prompt-Result Analysis Engine
Analyzes all prompts for relevancy and accuracy.
"""

import re
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
import time

def extract_prompt_data(block: str, prompt_num: int) -> Optional[Dict[str, Any]]:
    """Extract prompt data from a block."""
    data = {'prompt_num': prompt_num}
    
    # Extract INPUT
    input_match = re.search(r'INPUT\s*:\s*"([^"]*)"', block)
    if not input_match:
        return None
    data['input'] = input_match.group(1)
    
    # Extract VIBE and SECONDARY
    vibe_match = re.search(r'VIBE\s*:\s*(\w+)\s*\((\d+)%\s*conf\)', block)
    if vibe_match:
        data['vibe'] = vibe_match.group(1)
        data['vibe_confidence'] = int(vibe_match.group(2))
    
    secondary_match = re.search(r'SECONDARY:\s*(\w+)\s*\((\d+)%\)', block)
    if secondary_match:
        data['secondary_vibe'] = secondary_match.group(1)
        data['secondary_confidence'] = int(secondary_match.group(2))
    
    # Extract GENRES
    genres_match = re.search(r'GENRES\s*:\s*(.+?)(?:\nBPM_RNG|$)', block, re.DOTALL)
    if genres_match:
        genres_str = genres_match.group(1).strip()
        data['genres'] = [g.strip() for g in genres_str.split(',')]
    
    # Extract BPM_RNG
    bpm_match = re.search(r'BPM_RNG\s*:\s*(\d+)-(\d+)', block)
    if bpm_match:
        data['bpm_range'] = (int(bpm_match.group(1)), int(bpm_match.group(2)))
    
    # Extract POOL_SZ
    pool_match = re.search(r'POOL_SZ\s*:\s*(\d+)\s*raw\s*→\s*(\d+)\s*scored', block)
    if pool_match:
        data['pool_size'] = int(pool_match.group(1))
        data['returned_count'] = int(pool_match.group(2))
    
    # Extract LIMIT
    limit_match = re.search(r'LIMIT\s*:\s*(\d+)', block)
    if limit_match:
        data['limit'] = int(limit_match.group(1))
    
    # Extract TRACKS
    tracks = []
    track_pattern = r'\s+(\d+)\.\s+\[\s*(\d+(?:\.\d+)?)\]\s+(.+?)\s+—\s+(.+?)(?:\n|$)'
    for match in re.finditer(track_pattern, block):
        tracks.append({
            'rank': int(match.group(1)),
            'score': float(match.group(2)),
            'track': match.group(3).strip(),
            'artist': match.group(4).strip(),
        })
    data['tracks'] = tracks
    
    return data

def analyze_relevancy(prompt_data: Dict[str, Any]) -> float:
    """Calculate relevancy score using heuristics."""
    tracks = prompt_data.get('tracks', [])
    
    score = 50  # Base score
    
    # Check 1: Top track has good score (40% weight)
    if tracks:
        top_score = tracks[0]['score']
        if top_score >= 80:
            score += 20
        elif top_score >= 50:
            score += 10
        elif top_score < 30:
            score -= 15
    
    # Check 2: High-scoring tracks ratio (30% weight)
    high_score_count = sum(1 for t in tracks if t['score'] >= 50) if tracks else 0
    ratio = high_score_count / max(len(tracks), 1)
    if ratio >= 0.7:
        score += 15
    elif ratio >= 0.5:
        score += 8
    elif ratio < 0.3:
        score -= 10
    
    # Check 3: Track count vs requested (20% weight)
    limit = prompt_data.get('limit', 5)
    returned = len(tracks)
    if returned >= limit * 0.8:
        score += 10
    else:
        score -= 5
    
    # Check 4: Score spread quality (10% weight)
    if tracks and len(tracks) > 1:
        scores = [t['score'] for t in tracks]
        avg_score = sum(scores) / len(scores)
        if 40 <= avg_score <= 85:
            score += 5
    
    score = max(0, min(100, score))
    return score

def analyze_accuracy(prompt_data: Dict[str, Any]) -> float:
    """Calculate accuracy score using metadata checks."""
    tracks = prompt_data.get('tracks', [])
    checks_passed = 0
    total_checks = 0
    
    # Check 1: Score ordering
    total_checks += 1
    if len(tracks) > 1:
        is_ordered = all(
            tracks[i]['score'] >= tracks[i+1]['score'] 
            for i in range(len(tracks)-1)
        )
        if is_ordered:
            checks_passed += 1
    else:
        checks_passed += 1
    
    # Check 2: Score ranges valid
    total_checks += 1
    if all(0 <= t['score'] <= 200 for t in tracks):
        checks_passed += 1
    
    # Check 3: Track count matches
    total_checks += 1
    limit = min(prompt_data.get('limit', 5), prompt_data.get('returned_count', len(tracks)))
    if len(tracks) == limit or len(tracks) <= limit:
        checks_passed += 1
    
    # Check 4: Vibe detected
    total_checks += 1
    vibe = prompt_data.get('vibe', '')
    if vibe and vibe.lower() != 'unknown':
        checks_passed += 1
    
    # Check 5: Confidence reasonable
    total_checks += 1
    vibe_conf = prompt_data.get('vibe_confidence', 0)
    secondary_conf = prompt_data.get('secondary_confidence', 0)
    if 0 <= vibe_conf <= 100 and 0 <= secondary_conf <= 100:
        checks_passed += 1
    
    accuracy = (checks_passed / total_checks * 100) if total_checks > 0 else 0
    return accuracy

def parse_log_file(log_file: str) -> List[Dict[str, Any]]:
    """Parse log file and extract all prompts."""
    print("[LOG] Parsing file: {}".format(log_file))
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    prompt_blocks = re.split(r'--- \[PROMPT \d+/\d+\] ---', content)
    
    prompts = []
    for idx, block in enumerate(prompt_blocks[1:], 1):
        data = extract_prompt_data(block, idx)
        if data:
            prompts.append(data)
            if idx % 2000 == 0:
                print("[OK] Parsed {} prompts...".format(idx))
    
    print("[OK] Total prompts extracted: {}".format(len(prompts)))
    return prompts

def main():
    print("=" * 90)
    print("VIBEFINDER AI - PROMPT-RESULT ANALYSIS ENGINE")
    print("=" * 90)
    print()
    
    log_file = 'qa_batch_v10k_3.log'
    output_dir = 'analysis_reports'
    
    # Parse log
    start_time = time.time()
    prompts = parse_log_file(log_file)
    
    # Analyze
    print("[LOG] Analyzing {} prompts...".format(len(prompts)))
    analyses = []
    relevancy_scores = []
    accuracy_scores = []
    vibe_stats = defaultdict(lambda: {'count': 0, 'rel_sum': 0, 'acc_sum': 0})
    
    for idx, prompt in enumerate(prompts, 1):
        rel_score = analyze_relevancy(prompt)
        acc_score = analyze_accuracy(prompt)
        
        analyses.append({
            'prompt_num': prompt['prompt_num'],
            'input': prompt.get('input', '')[:80],
            'vibe': prompt.get('vibe', ''),
            'relevancy': rel_score,
            'accuracy': acc_score,
            'track_count': len(prompt.get('tracks', [])),
        })
        
        relevancy_scores.append(rel_score)
        accuracy_scores.append(acc_score)
        
        vibe = prompt.get('vibe', '')
        if vibe:
            vibe_stats[vibe]['count'] += 1
            vibe_stats[vibe]['rel_sum'] += rel_score
            vibe_stats[vibe]['acc_sum'] += acc_score
        
        if (idx) % 2000 == 0:
            print("[OK] Analyzed {}/{} prompts...".format(idx, len(prompts)))
    
    # Calculate metrics
    avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0
    avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0
    
    high_rel = sum(1 for s in relevancy_scores if s >= 80)
    medium_rel = sum(1 for s in relevancy_scores if 50 <= s < 80)
    low_rel = sum(1 for s in relevancy_scores if s < 50)
    
    high_acc = sum(1 for s in accuracy_scores if s >= 80)
    medium_acc = sum(1 for s in accuracy_scores if 50 <= s < 80)
    low_acc = sum(1 for s in accuracy_scores if s < 50)
    
    # Generate reports
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Summary report
    summary_file = os.path.join(output_dir, "SUMMARY_{}.txt".format(timestamp))
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("=" * 90 + "\n")
        f.write("VIBEFINDER AI - PROMPT-RESULT ANALYSIS REPORT\n")
        f.write("=" * 90 + "\n\n")
        
        f.write("Analysis Date: {}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        f.write("Log File: {}\n".format(log_file))
        f.write("Total Prompts: {}\n\n".format(len(prompts)))
        
        f.write("RELEVANCY METRICS:\n")
        f.write("  Average Score: {:.1f}%\n".format(avg_relevancy))
        f.write("  High (>=80%): {} ({:.1f}%)\n".format(high_rel, high_rel/len(prompts)*100))
        f.write("  Medium (50-79%): {} ({:.1f}%)\n".format(medium_rel, medium_rel/len(prompts)*100))
        f.write("  Low (<50%): {} ({:.1f}%)\n\n".format(low_rel, low_rel/len(prompts)*100))
        
        f.write("ACCURACY METRICS:\n")
        f.write("  Average Score: {:.1f}%\n".format(avg_accuracy))
        f.write("  High (>=80%): {} ({:.1f}%)\n".format(high_acc, high_acc/len(prompts)*100))
        f.write("  Medium (50-79%): {} ({:.1f}%)\n".format(medium_acc, medium_acc/len(prompts)*100))
        f.write("  Low (<50%): {} ({:.1f}%)\n\n".format(low_acc, low_acc/len(prompts)*100))
        
        f.write("PERFORMANCE BY VIBE:\n")
        for vibe, stats in sorted(vibe_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            count = stats['count']
            avg_rel = stats['rel_sum'] / count if count > 0 else 0
            avg_acc = stats['acc_sum'] / count if count > 0 else 0
            f.write("  {}: count={}, rel={:.1f}%, acc={:.1f}%\n".format(vibe.upper(), count, avg_rel, avg_acc))
        
        f.write("\n" + "=" * 90 + "\n")
    
    # CSV report
    csv_file = os.path.join(output_dir, "DATA_{}.csv".format(timestamp))
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write("PromptNum,Input,Vibe,Relevancy,Accuracy,TrackCount\n")
        for a in analyses:
            f.write('{},{},{},{:.1f},{:.1f},{}\n'.format(
                a['prompt_num'],
                '"{}"'.format(a['input'].replace('"', "'")),
                a['vibe'],
                a['relevancy'],
                a['accuracy'],
                a['track_count']
            ))
    
    # JSON report  
    json_file = os.path.join(output_dir, "DETAILED_{}.json".format(timestamp))
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_prompts': len(prompts),
                'log_file': log_file
            },
            'metrics': {
                'avg_relevancy': avg_relevancy,
                'avg_accuracy': avg_accuracy,
                'high_relevancy': high_rel,
                'medium_relevancy': medium_rel,
                'low_relevancy': low_rel,
                'high_accuracy': high_acc,
                'medium_accuracy': medium_acc,
                'low_accuracy': low_acc,
            },
            'sample': analyses[:20]
        }, f, indent=2, ensure_ascii=False)
    
    elapsed = time.time() - start_time
    print("\n[OK] Analysis complete!")
    print("\nKey Metrics:")
    print("  - Total Prompts: {}".format(len(prompts)))
    print("  - Avg Relevancy: {:.1f}%".format(avg_relevancy))
    print("  - Avg Accuracy: {:.1f}%".format(avg_accuracy))
    print("\nReports saved to: {}".format(output_dir))
    print("  - {}".format(summary_file))
    print("  - {}".format(csv_file))
    print("  - {}".format(json_file))
    print("\nTime elapsed: {:.1f}s".format(elapsed))

if __name__ == '__main__':
    main()
