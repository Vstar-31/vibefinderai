#!/usr/bin/env python3
"""
VIBEFINDER AI - Interactive Analysis Tool
Drill down into specific prompts and vibes for detailed investigation.
"""

import csv
import json
import os
from pathlib import Path
from collections import defaultdict

def load_csv_data(csv_file):
    """Load analysis data from CSV."""
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'prompt_num': int(row['PromptNum']),
                'input': row['Input'].strip('"'),
                'vibe': row['Vibe'],
                'relevancy': float(row['Relevancy']),
                'accuracy': float(row['Accuracy']),
                'track_count': int(row['TrackCount']),
            })
    return data

def analyze_by_vibe(data, target_vibe):
    """Analyze all prompts for a specific vibe."""
    vibe_data = [d for d in data if d['vibe'].lower() == target_vibe.lower()]
    
    if not vibe_data:
        return None
    
    relevancy_scores = [d['relevancy'] for d in vibe_data]
    accuracy_scores = [d['accuracy'] for d in vibe_data]
    
    avg_rel = sum(relevancy_scores) / len(relevancy_scores)
    avg_acc = sum(accuracy_scores) / len(accuracy_scores)
    
    low_rel = [d for d in vibe_data if d['relevancy'] < 50]
    high_rel = [d for d in vibe_data if d['relevancy'] >= 80]
    
    return {
        'vibe': target_vibe,
        'count': len(vibe_data),
        'avg_relevancy': avg_rel,
        'avg_accuracy': avg_acc,
        'high_performers': len(high_rel),
        'low_performers': len(low_rel),
        'low_rel_prompts': sorted(low_rel, key=lambda x: x['relevancy'])[:10],
        'high_rel_prompts': sorted(high_rel, key=lambda x: x['relevancy'], reverse=True)[:10],
        'track_count_stats': {
            'avg': sum(d['track_count'] for d in vibe_data) / len(vibe_data),
            'min': min(d['track_count'] for d in vibe_data),
            'max': max(d['track_count'] for d in vibe_data),
        }
    }

def generate_vibe_reports(csv_file, output_dir='analysis_reports'):
    """Generate detailed reports for each vibe."""
    data = load_csv_data(csv_file)
    
    # Group by vibe
    vibes = set(d['vibe'] for d in data)
    
    report_file = Path(output_dir) / "VIBE_ANALYSIS_DETAILED.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("VIBEFINDER AI - DETAILED VIBE ANALYSIS\n")
        f.write("=" * 100 + "\n\n")
        
        for vibe in sorted(vibes):
            analysis = analyze_by_vibe(data, vibe)
            if not analysis:
                continue
            
            f.write("VIBE: {}\n".format(vibe.upper()))
            f.write("-" * 100 + "\n")
            f.write("  Total Prompts: {}\n".format(analysis['count']))
            f.write("  Average Relevancy: {:.1f}%\n".format(analysis['avg_relevancy']))
            f.write("  Average Accuracy: {:.1f}%\n".format(analysis['avg_accuracy']))
            f.write("  High Performers (>=80%): {} ({:.1f}%)\n".format(
                analysis['high_performers'],
                analysis['high_performers'] / max(analysis['count'], 1) * 100
            ))
            f.write("  Low Performers (<50%): {} ({:.1f}%)\n".format(
                analysis['low_performers'],
                analysis['low_performers'] / max(analysis['count'], 1) * 100
            ))
            f.write("  Track Count: avg={:.0f}, min={}, max={}\n\n".format(
                analysis['track_count_stats']['avg'],
                analysis['track_count_stats']['min'],
                analysis['track_count_stats']['max']
            ))
            
            if analysis['low_performers'] > 0:
                f.write("  TOP 10 LOWEST RELEVANCY PROMPTS:\n")
                for i, prompt in enumerate(analysis['low_rel_prompts'][:10], 1):
                    f.write("    {}. [Score: {:.0f}] {} (Prompt #{})\n".format(
                        i, 
                        prompt['relevancy'],
                        prompt['input'][:60] + ('...' if len(prompt['input']) > 60 else ''),
                        prompt['prompt_num']
                    ))
                f.write("\n")
            
            if analysis['high_performers'] > 0:
                f.write("  TOP 10 HIGHEST RELEVANCY PROMPTS:\n")
                for i, prompt in enumerate(analysis['high_rel_prompts'][:10], 1):
                    f.write("    {}. [Score: {:.0f}] {} (Prompt #{})\n".format(
                        i,
                        prompt['relevancy'],
                        prompt['input'][:60] + ('...' if len(prompt['input']) > 60 else ''),
                        prompt['prompt_num']
                    ))
                f.write("\n")
            
            f.write("\n")
        
        f.write("=" * 100 + "\n")
    
    print("[OK] Vibe analysis report: {}".format(report_file))

def generate_problem_prompts_report(csv_file, output_dir='analysis_reports'):
    """Identify and report on problematic prompts."""
    data = load_csv_data(csv_file)
    
    # Find problems
    low_relevancy = [d for d in data if d['relevancy'] < 50]
    low_accuracy = [d for d in data if d['accuracy'] < 80]
    very_low = [d for d in data if d['relevancy'] < 35]
    
    report_file = Path(output_dir) / "PROBLEM_PROMPTS_ANALYSIS.txt"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=" * 100 + "\n")
        f.write("VIBEFINDER AI - PROBLEM PROMPTS ANALYSIS\n")
        f.write("=" * 100 + "\n\n")
        
        f.write("SUMMARY:\n")
        f.write("  Low Relevancy (<50%): {} prompts ({:.2f}%)\n".format(
            len(low_relevancy), len(low_relevancy)/len(data)*100
        ))
        f.write("  Very Low Relevancy (<35%): {} prompts ({:.2f}%)\n".format(
            len(very_low), len(very_low)/len(data)*100
        ))
        f.write("  Low Accuracy (<80%): {} prompts ({:.2f}%)\n\n".format(
            len(low_accuracy), len(low_accuracy)/len(data)*100
        ))
        
        # Group low relevancy by vibe
        low_by_vibe = defaultdict(list)
        for p in low_relevancy:
            low_by_vibe[p['vibe']].append(p)
        
        f.write("LOW RELEVANCY BY VIBE:\n")
        for vibe in sorted(low_by_vibe.keys(), key=lambda x: len(low_by_vibe[x]), reverse=True):
            prompts = low_by_vibe[vibe]
            f.write("\n  {}: {} prompts\n".format(vibe.upper(), len(prompts)))
            f.write("    Sample problematic prompts:\n")
            for p in sorted(prompts, key=lambda x: x['relevancy'])[:5]:
                f.write("      Prompt #{}: [Score: {:.0f}] {}\n".format(
                    p['prompt_num'],
                    p['relevancy'],
                    p['input'][:70] + ('...' if len(p['input']) > 70 else '')
                ))
        
        f.write("\n" + "-" * 100 + "\n")
        f.write("VERY LOW RELEVANCY (<35%) - CRITICAL REVIEW:\n")
        for p in sorted(very_low, key=lambda x: x['relevancy'])[:20]:
            f.write("  Prompt #{}: [VIBE: {}] [Score: {:.0f}] {}\n".format(
                p['prompt_num'],
                p['vibe'],
                p['relevancy'],
                p['input']
            ))
        
        f.write("\n" + "=" * 100 + "\n")
    
    print("[OK] Problem prompts report: {}".format(report_file))

def main():
    print("=" * 100)
    print("VIBEFINDER AI - INTERACTIVE ANALYSIS TOOL")
    print("=" * 100 + "\n")
    
    output_dir = 'analysis_reports'
    
    # Find the latest CSV file
    csv_files = list(Path(output_dir).glob('DATA_*.csv'))
    if not csv_files:
        print("[ERROR] No CSV data file found in {}".format(output_dir))
        return
    
    csv_file = str(csv_files[-1])  # Most recent
    print("[LOG] Loading data from: {}".format(csv_file))
    
    # Generate detailed reports
    generate_vibe_reports(csv_file, output_dir)
    generate_problem_prompts_report(csv_file, output_dir)
    
    print("[OK] Analysis complete!")
    print("\nNew reports generated:")
    print("  - VIBE_ANALYSIS_DETAILED.txt")
    print("  - PROBLEM_PROMPTS_ANALYSIS.txt")

if __name__ == '__main__':
    main()
