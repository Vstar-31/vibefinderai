#!/usr/bin/env python3
"""
VIBEFINDER AI — ADVANCED PROMPT-RESULT ANALYSIS ENGINE
Analyzes every prompt-result combination with caching, batching, and detailed metrics.
"""

import re
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from collections import defaultdict
import pickle
import time

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[WARNING] Gemini API not available - using heuristic analysis only")

class AdvancedPromptAnalyzer:
    def __init__(self, log_file: str, config_file: str = "analyzer_config.json", output_dir: str = "analysis_reports"):
        self.log_file = log_file
        self.config_file = config_file
        self.output_dir = output_dir
        self.prompts_data = []
        self.analyses = []
        self.cache = {}
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize Gemini if available
        if GEMINI_AVAILABLE and os.getenv('GOOGLE_API_KEY'):
            genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
            self.model = genai.GenerativeModel(self.config['gemini']['model'])
        else:
            self.model = None
        
        # Initialize metrics
        self.metrics = self._init_metrics()
        self.vibe_stats = defaultdict(lambda: {'count': 0, 'avg_relevancy': 0, 'avg_accuracy': 0})
        self.genre_stats = defaultdict(lambda: {'count': 0, 'avg_relevancy': 0})
        
        os.makedirs(output_dir, exist_ok=True)
        self._load_cache()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[WARNING] Config file not found: {self.config_file}, using defaults")
            return {
                'analysis': {
                    'batch_size': 50,
                    'max_retries': 3,
                    'timeout_per_prompt': 30,
                    'cache_results': True,
                    'cache_file': 'analysis_cache.pkl'
                },
                'relevancy': {
                    'weight_track_matching': 0.4,
                    'weight_vibe_alignment': 0.3,
                    'weight_genre_alignment': 0.2,
                    'weight_overall_coherence': 0.1,
                    'high_threshold': 80,
                    'medium_threshold': 50
                },
                'accuracy': {},
                'gemini': {'model': 'gemini-1.5-flash', 'temperature': 0.7, 'max_output_tokens': 500},
                'output': {'format': ['json', 'csv', 'txt']}
            }

    def _init_metrics(self) -> Dict[str, Any]:
        """Initialize metrics dictionary."""
        return {
            'total_prompts': 0,
            'analyzed_prompts': 0,
            'high_relevancy': 0,
            'medium_relevancy': 0,
            'low_relevancy': 0,
            'high_accuracy': 0,
            'medium_accuracy': 0,
            'low_accuracy': 0,
            'avg_relevancy_score': 0.0,
            'avg_accuracy_score': 0.0,
            'total_relevancy_sum': 0.0,
            'total_accuracy_sum': 0.0,
            'by_vibe': {},
            'by_genre': {},
        }

    def _load_cache(self):
        """Load cached analyses."""
        cache_file = Path(self.output_dir) / self.config['analysis']['cache_file']
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                print(f"✓ Loaded cache with {len(self.cache)} entries")
            except Exception as e:
                print(f"⚠️ Could not load cache: {e}")

    def _save_cache(self):
        """Save cache to file."""
        cache_file = Path(self.output_dir) / self.config['analysis']['cache_file']
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(self.cache, f)
        except Exception as e:
            print(f"⚠️ Could not save cache: {e}")

    def parse_log_file(self) -> List[Dict[str, Any]]:
        """Parse the log file to extract all prompts and their results."""
        print(f"[LOG] Parsing log file: {self.log_file}")
        
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Split by prompt markers
        prompt_blocks = re.split(r'--- \[PROMPT \d+/\d+\] ---', content)
        
        for idx, block in enumerate(prompt_blocks[1:], 1):  # Skip header
            prompt_data = self._extract_prompt_data(block, idx)
            if prompt_data:
                self.prompts_data.append(prompt_data)
                if idx % 2000 == 0:
                    print(f"  [OK] Parsed {idx} prompts...")
        
        self.metrics['total_prompts'] = len(self.prompts_data)
        print(f"[OK] Total prompts extracted: {len(self.prompts_data)}")
        return self.prompts_data

    def _extract_prompt_data(self, block: str, prompt_num: int) -> Optional[Dict[str, Any]]:
        """Extract prompt data from a block."""
        data = {'prompt_num': prompt_num}
        
        # Extract INPUT
        input_match = re.search(r'INPUT\s*:\s*"([^"]*)"', block)
        if not input_match:
            return None
        data['input'] = input_match.group(1)
        
        # Extract LANGUAGE
        lang_match = re.search(r'LANGUAGE\s*:\s*(\w+)', block)
        data['language'] = lang_match.group(1) if lang_match else 'Unknown'
        
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
        
        # Extract additional metadata
        tag_match = re.search(r'TAG_USED\s*:\s*(.+?)(?:\nGENRES|$)', block)
        if tag_match:
            data['tag_used'] = tag_match.group(1).strip()
        
        limit_match = re.search(r'LIMIT\s*:\s*(\d+)', block)
        if limit_match:
            data['limit'] = int(limit_match.group(1))
        
        return data

    def analyze_relevancy_heuristic(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze relevancy using heuristic scoring (no API call)."""
        input_text = prompt_data.get('input', '').lower()
        vibe = prompt_data.get('vibe', '').lower()
        genres = [g.lower() for g in prompt_data.get('genres', [])]
        tracks = prompt_data.get('tracks', [])
        
        score = 50  # Base score
        issues = []
        
        # Check 1: Top track has decent score (weighted 40%)
        if tracks and tracks[0]['score'] >= 70:
            score += 15
        elif tracks and tracks[0]['score'] < 30:
            score -= 10
            issues.append('Top track has low score')
        else:
            score += 5
        
        # Check 2: Multiple high-scoring tracks (weighted 30%)
        high_score_count = sum(1 for t in tracks if t['score'] >= 50)
        if high_score_count / max(len(tracks), 1) >= 0.6:
            score += 10
        else:
            issues.append('Low proportion of high-scoring tracks')
        
        # Check 3: Minimum track count (weighted 20%)
        if len(tracks) >= prompt_data.get('limit', 5) * 0.8:
            score += 10
        else:
            issues.append('Fewer tracks returned than requested')
        
        # Check 4: Score distribution (weighted 10%)
        if len(tracks) > 1:
            avg_score = sum(t['score'] for t in tracks) / len(tracks)
            if 30 <= avg_score <= 80:
                score += 5
        
        # Normalize to 0-100
        score = max(0, min(100, score))
        
        return {
            'relevancy_score': score,
            'method': 'heuristic',
            'track_alignment': f'{len([t for t in tracks if t["score"] >= 50])}/{len(tracks)} tracks have score ≥50',
            'issues': issues,
            'suggestions': self._suggest_improvements(prompt_data),
        }

    def _suggest_improvements(self, prompt_data: Dict[str, Any]) -> List[str]:
        """Suggest improvements based on analysis."""
        suggestions = []
        
        input_text = prompt_data.get('input', '')
        vibe = prompt_data.get('vibe', '')
        tracks = prompt_data.get('tracks', [])
        
        if len(tracks) < prompt_data.get('limit', 5):
            suggestions.append('Expand pool size to find more matching tracks')
        
        if tracks and tracks[0]['score'] < 50:
            suggestions.append('Consider adjusting search parameters or weights')
        
        if vibe and vibe.lower() in ['unknown', 'mixed']:
            suggestions.append('Input may be ambiguous - try more specific descriptors')
        
        return suggestions

    def analyze_accuracy(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze accuracy using metadata checks."""
        tracks = prompt_data.get('tracks', [])
        accuracy_checks = {}
        
        # Check 1: Score order
        if len(tracks) > 1:
            is_ordered = all(
                tracks[i]['score'] >= tracks[i+1]['score'] 
                for i in range(len(tracks)-1)
            )
            accuracy_checks['score_order_valid'] = is_ordered
        else:
            accuracy_checks['score_order_valid'] = True
        
        # Check 2: Score ranges
        accuracy_checks['score_ranges_valid'] = all(
            0 <= t['score'] <= 200 for t in tracks
        )
        
        # Check 3: Track count
        accuracy_checks['track_count_matches'] = len(tracks) == min(
            prompt_data.get('limit', 5),
            prompt_data.get('returned_count', len(tracks))
        )
        
        # Check 4: Vibe detection
        accuracy_checks['vibe_detected'] = bool(
            prompt_data.get('vibe') and 
            prompt_data.get('vibe').lower() != 'unknown'
        )
        
        # Check 5: Confidence scores reasonable
        accuracy_checks['confidence_valid'] = all(
            0 <= prompt_data.get('vibe_confidence', 0) <= 100,
            0 <= prompt_data.get('secondary_confidence', 0) <= 100
        ) if len([1 for _ in []]) == 0 else True
        
        # Calculate overall accuracy
        passed = sum(accuracy_checks.values())
        total = len(accuracy_checks)
        accuracy_score = (passed / total * 100) if total > 0 else 0
        
        return {
            'accuracy_score': accuracy_score,
            'checks': accuracy_checks,
            'issues': [k for k, v in accuracy_checks.items() if not v],
        }

    def analyze_all_prompts(self):
        """Analyze all prompts."""
        print(f"\n🔍 Analyzing {len(self.prompts_data)} prompts for relevancy and accuracy...")
        
        batch_size = self.config['analysis']['batch_size']
        
        for idx, prompt_data in enumerate(self.prompts_data, 1):
            # Check cache first
            cache_key = f"prompt_{prompt_data['prompt_num']}"
            if cache_key in self.cache:
                analysis_entry = self.cache[cache_key]
            else:
                relevancy = self.analyze_relevancy_heuristic(prompt_data)
                accuracy = self.analyze_accuracy(prompt_data)
                
                analysis_entry = {
                    'prompt_num': prompt_data['prompt_num'],
                    'input': prompt_data.get('input', '')[:100],  # Truncate
                    'vibe': prompt_data.get('vibe', ''),
                    'relevancy': relevancy,
                    'accuracy': accuracy,
                    'timestamp': datetime.now().isoformat(),
                }
                
                if self.config['analysis']['cache_results']:
                    self.cache[cache_key] = analysis_entry
            
            self.analyses.append(analysis_entry)
            
            # Update metrics
            rel_score = analysis_entry['relevancy']['relevancy_score']
            acc_score = analysis_entry['accuracy']['accuracy_score']
            
            self.metrics['total_relevancy_sum'] += rel_score
            self.metrics['total_accuracy_sum'] += acc_score
            self.metrics['analyzed_prompts'] += 1
            
            # Categorize relevancy
            high_threshold = self.config['relevancy']['high_threshold']
            medium_threshold = self.config['relevancy']['medium_threshold']
            
            if rel_score >= high_threshold:
                self.metrics['high_relevancy'] += 1
            elif rel_score >= medium_threshold:
                self.metrics['medium_relevancy'] += 1
            else:
                self.metrics['low_relevancy'] += 1
            
            # Categorize accuracy
            if acc_score >= high_threshold:
                self.metrics['high_accuracy'] += 1
            elif acc_score >= medium_threshold:
                self.metrics['medium_accuracy'] += 1
            else:
                self.metrics['low_accuracy'] += 1
            
            # Track by vibe
            vibe = analysis_entry['vibe']
            if vibe:
                if vibe not in self.metrics['by_vibe']:
                    self.metrics['by_vibe'][vibe] = {'count': 0, 'rel_sum': 0, 'acc_sum': 0}
                self.metrics['by_vibe'][vibe]['count'] += 1
                self.metrics['by_vibe'][vibe]['rel_sum'] += rel_score
                self.metrics['by_vibe'][vibe]['acc_sum'] += acc_score
            
            if idx % 2000 == 0:
                print(f"  [OK] Analyzed {idx}/{len(self.prompts_data)} prompts...")
        
        # Calculate final metrics
        if self.metrics['analyzed_prompts'] > 0:
            self.metrics['avg_relevancy_score'] = self.metrics['total_relevancy_sum'] / self.metrics['analyzed_prompts']
            self.metrics['avg_accuracy_score'] = self.metrics['total_accuracy_sum'] / self.metrics['analyzed_prompts']
        
        print(f"[OK] Analysis complete!")
        self._save_cache()

    def generate_reports(self):
        """Generate comprehensive analysis reports."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Summary text report
        summary_file = Path(self.output_dir) / f"ANALYSIS_SUMMARY_{timestamp}.txt"
        self._write_summary_report(summary_file)
        
        # Detailed JSON report
        json_file = Path(self.output_dir) / f"analysis_detailed_{timestamp}.json"
        self._write_json_report(json_file)
        
        # CSV for spreadsheet analysis
        csv_file = Path(self.output_dir) / f"analysis_data_{timestamp}.csv"
        self._write_csv_report(csv_file)
        
        # Vibe analysis breakdown
        vibe_file = Path(self.output_dir) / f"analysis_by_vibe_{timestamp}.txt"
        self._write_vibe_analysis(vibe_file)
        
        # Issues report
        issues_file = Path(self.output_dir) / f"analysis_issues_{timestamp}.txt"
        self._write_issues_report(issues_file)
        
        print(f"\n[REPORT] Reports generated:")
        print(f"  - {summary_file}")
        print(f"  - {json_file}")
        print(f"  - {csv_file}")
        print(f"  - {vibe_file}")
        print(f"  - {issues_file}")
        
        return [summary_file, json_file, csv_file, vibe_file, issues_file]

    def _write_summary_report(self, filepath: Path):
        """Write summary report."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*90 + "\n")
            f.write("VIBEFINDER AI — PROMPT-RESULT ANALYSIS REPORT\n")
            f.write("="*90 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Log File: {self.log_file}\n")
            f.write(f"Total Prompts: {self.metrics['total_prompts']}\n\n")
            
            f.write("RELEVANCY ANALYSIS:\n")
            f.write(f"  Average Score: {self.metrics['avg_relevancy_score']:.1f}%\n")
            total = max(self.metrics['total_prompts'], 1)
            f.write(f"  High Relevancy (≥{self.config['relevancy']['high_threshold']}%): {self.metrics['high_relevancy']} ({self.metrics['high_relevancy']/total*100:.1f}%)\n")
            f.write(f"  Medium Relevancy: {self.metrics['medium_relevancy']} ({self.metrics['medium_relevancy']/total*100:.1f}%)\n")
            f.write(f"  Low Relevancy: {self.metrics['low_relevancy']} ({self.metrics['low_relevancy']/total*100:.1f}%)\n\n")
            
            f.write("ACCURACY ANALYSIS:\n")
            f.write(f"  Average Score: {self.metrics['avg_accuracy_score']:.1f}%\n")
            f.write(f"  High Accuracy (≥{self.config['relevancy']['high_threshold']}%): {self.metrics['high_accuracy']} ({self.metrics['high_accuracy']/total*100:.1f}%)\n")
            f.write(f"  Medium Accuracy: {self.metrics['medium_accuracy']} ({self.metrics['medium_accuracy']/total*100:.1f}%)\n")
            f.write(f"  Low Accuracy: {self.metrics['low_accuracy']} ({self.metrics['low_accuracy']/total*100:.1f}%)\n\n")
            
            f.write("PERFORMANCE BY VIBE:\n")
            for vibe, stats in sorted(self.metrics['by_vibe'].items(), key=lambda x: x[1]['count'], reverse=True):
                avg_rel = stats['rel_sum'] / stats['count'] if stats['count'] > 0 else 0
                avg_acc = stats['acc_sum'] / stats['count'] if stats['count'] > 0 else 0
                f.write(f"  {vibe.upper()}:\n")
                f.write(f"    Count: {stats['count']}\n")
                f.write(f"    Avg Relevancy: {avg_rel:.1f}%\n")
                f.write(f"    Avg Accuracy: {avg_acc:.1f}%\n\n")
            
            f.write("="*90 + "\n")

    def _write_json_report(self, filepath: Path):
        """Write detailed JSON report."""
        report_data = {
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_prompts': self.metrics['total_prompts'],
                'analyzed_prompts': self.metrics['analyzed_prompts'],
                'log_file': self.log_file,
            },
            'metrics': {k: v for k, v in self.metrics.items() if k not in ['by_vibe']},
            'sample_analyses': self.analyses[:20],  # First 20 for detail
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

    def _write_csv_report(self, filepath: Path):
        """Write CSV report for spreadsheet analysis."""
        with open(filepath, 'w', encoding='utf-8', newline='') as f:
            f.write("PromptNum,Input,Vibe,RelevancyScore,AccuracyScore,ScoreOrder,RelevancyCategory\n")
            for analysis in self.analyses:
                prompt_num = analysis['prompt_num']
                input_text = analysis['input'].replace(',', ';').replace('"', "'")
                vibe = analysis['vibe']
                rel_score = analysis['relevancy']['relevancy_score']
                acc_score = analysis['accuracy']['accuracy_score']
                score_order = analysis['accuracy']['checks'].get('score_order_valid', 'Unknown')
                
                high_threshold = self.config['relevancy']['high_threshold']
                medium_threshold = self.config['relevancy']['medium_threshold']
                if rel_score >= high_threshold:
                    category = "High"
                elif rel_score >= medium_threshold:
                    category = "Medium"
                else:
                    category = "Low"
                
                f.write(f'{prompt_num},"{input_text}",{vibe},{rel_score:.1f},{acc_score:.1f},{score_order},{category}\n')

    def _write_vibe_analysis(self, filepath: Path):
        """Write vibe-by-vibe analysis."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*90 + "\n")
            f.write("VIBEFINDER AI — VIBE PERFORMANCE BREAKDOWN\n")
            f.write("="*90 + "\n\n")
            
            for vibe, stats in sorted(self.metrics['by_vibe'].items(), key=lambda x: x[1]['count'], reverse=True):
                count = stats['count']
                avg_rel = stats['rel_sum'] / count if count > 0 else 0
                avg_acc = stats['acc_sum'] / count if count > 0 else 0
                
                f.write(f"VIBE: {vibe.upper()}\n")
                f.write(f"  Prompt Count: {count}\n")
                f.write(f"  Average Relevancy Score: {avg_rel:.1f}%\n")
                f.write(f"  Average Accuracy Score: {avg_acc:.1f}%\n")
                f.write(f"  Performance Level: {'EXCELLENT' if avg_rel >= 80 else 'GOOD' if avg_rel >= 60 else 'NEEDS WORK'}\n\n")

    def _write_issues_report(self, filepath: Path):
        """Write consolidated issues report."""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("="*90 + "\n")
            f.write("VIBEFINDER AI — ISSUES & PROBLEM SUMMARY\n")
            f.write("="*90 + "\n\n")
            
            all_issues = defaultdict(int)
            low_relevancy_prompts = []
            low_accuracy_prompts = []
            
            for analysis in self.analyses:
                rel_score = analysis['relevancy']['relevancy_score']
                acc_score = analysis['accuracy']['accuracy_score']
                
                for issue in analysis['accuracy'].get('issues', []):
                    all_issues[issue] += 1
                
                if rel_score < 50:
                    low_relevancy_prompts.append({
                        'num': analysis['prompt_num'],
                        'input': analysis['input'],
                        'score': rel_score
                    })
                
                if acc_score < 50:
                    low_accuracy_prompts.append({
                        'num': analysis['prompt_num'],
                        'input': analysis['input'],
                        'score': acc_score
                    })
            
            f.write("COMMON ISSUES (by frequency):\n")
            for issue, count in sorted(all_issues.items(), key=lambda x: x[1], reverse=True)[:15]:
                f.write(f"  • {issue}: {count} occurrences ({count/max(self.metrics['analyzed_prompts'],1)*100:.1f}%)\n")
            
            f.write(f"\n\nLOW RELEVANCY PROMPTS (Score < 50): {len(low_relevancy_prompts)}\n")
            for prompt in low_relevancy_prompts[:20]:
                f.write(f"  Prompt {prompt['num']}: {prompt['input'][:70]}... (Score: {prompt['score']:.1f})\n")
            
            f.write(f"\n\nLOW ACCURACY PROMPTS (Score < 50): {len(low_accuracy_prompts)}\n")
            for prompt in low_accuracy_prompts[:20]:
                f.write(f"  Prompt {prompt['num']}: {prompt['input'][:70]}... (Score: {prompt['score']:.1f})\n")
            
            f.write("\n" + "="*90 + "\n")

    def run(self):
        """Run the complete analysis pipeline."""
        print("\n" + "="*90)
        print("VIBEFINDER AI - ADVANCED PROMPT-RESULT ANALYSIS ENGINE")
        print("="*90)
        
        start_time = time.time()
        
        self.parse_log_file()
        self.analyze_all_prompts()
        reports = self.generate_reports()
        
        elapsed = time.time() - start_time
        print(f"\n[OK] Analysis complete in {elapsed:.1f} seconds!")
        print(f"\nKey Metrics:")
        print(f"  - Total Prompts: {self.metrics['total_prompts']}")
        print(f"  - Average Relevancy: {self.metrics['avg_relevancy_score']:.1f}%")
        print(f"  - Average Accuracy: {self.metrics['avg_accuracy_score']:.1f}%")


if __name__ == '__main__':
    log_file = 'backend/qa_batch_v10k_3.log'
    analyzer = AdvancedPromptAnalyzer(log_file, output_dir='backend/analysis_reports')
    analyzer.run()
