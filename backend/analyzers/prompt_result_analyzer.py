#!/usr/bin/env python3
"""
VIBEFINDER AI — PROMPT-RESULT ANALYSIS ENGINE
Analyzes every prompt-result combination for relevancy and accuracy.
"""

import re
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import google.generativeai as genai

# Configure Gemini
genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
model = genai.GenerativeModel('gemini-1.5-flash')

class PromptResultAnalyzer:
    def __init__(self, log_file: str, output_dir: str = "analysis_reports"):
        self.log_file = log_file
        self.output_dir = output_dir
        self.prompts_data = []
        self.analyses = []
        self.metrics = {
            'total_prompts': 0,
            'high_relevancy': 0,
            'medium_relevancy': 0,
            'low_relevancy': 0,
            'high_accuracy': 0,
            'medium_accuracy': 0,
            'low_accuracy': 0,
            'avg_relevancy_score': 0,
            'avg_accuracy_score': 0,
        }
        os.makedirs(output_dir, exist_ok=True)

    def parse_log_file(self) -> List[Dict[str, Any]]:
        """Parse the log file to extract all prompts and their results."""
        print(f"📖 Parsing log file: {self.log_file}")
        
        with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Split by prompt markers
        prompt_blocks = re.split(r'--- \[PROMPT \d+/\d+\] ---', content)
        
        for idx, block in enumerate(prompt_blocks[1:], 1):  # Skip header
            prompt_data = self._extract_prompt_data(block, idx)
            if prompt_data:
                self.prompts_data.append(prompt_data)
                if idx % 1000 == 0:
                    print(f"  ✓ Parsed {idx} prompts...")
        
        print(f"✓ Total prompts extracted: {len(self.prompts_data)}")
        return self.prompts_data

    def _extract_prompt_data(self, block: str, prompt_num: int) -> Dict[str, Any]:
        """Extract prompt data from a block."""
        data = {'prompt_num': prompt_num}
        
        # Extract INPUT
        input_match = re.search(r'INPUT\s*:\s*"([^"]*)"', block)
        if input_match:
            data['input'] = input_match.group(1)
        
        # Extract LANGUAGE
        lang_match = re.search(r'LANGUAGE\s*:\s*(\w+)', block)
        if lang_match:
            data['language'] = lang_match.group(1)
        
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
        
        # Extract ENTITY (Artist/Song)
        entity_match = re.search(r'ENTITY\s*:\s*Artist=\[([^\]]*)\]\s*Song=\[([^\]]*)\]', block)
        if entity_match:
            data['entity_artist'] = entity_match.group(1) if entity_match.group(1) else None
            data['entity_song'] = entity_match.group(2) if entity_match.group(2) else None
        
        # Extract KNOBS
        knobs_match = re.search(r'KNOBS\s*:\s*(.+?)(?:\nLIMIT|$)', block)
        if knobs_match:
            knobs_str = knobs_match.group(1).strip()
            data['knobs'] = knobs_str
        
        # Extract TAG_USED
        tag_match = re.search(r'TAG_USED\s*:\s*(.+?)(?:\nGENRES|$)', block)
        if tag_match:
            data['tag_used'] = tag_match.group(1).strip()
        
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
        
        # Extract PRO MODE if present
        pro_mode_match = re.search(r'PRO MODE\s*:\s*(.+?)(?:\nVIBE|$)', block)
        if pro_mode_match:
            data['pro_mode'] = pro_mode_match.group(1).strip()
        
        return data if data.get('input') else None

    def analyze_relevancy(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze relevancy of results using Gemini."""
        input_text = prompt_data.get('input', '')
        vibe = prompt_data.get('vibe', 'unknown')
        genres = ', '.join(prompt_data.get('genres', [])[:5])  # Top 5 genres
        tracks_summary = '\n'.join([
            f"• {t['track']} by {t['artist']} (score: {t['score']})"
            for t in prompt_data.get('tracks', [])[:3]
        ])
        
        prompt = f"""
        Analyze the relevancy of these music recommendations for the user's request.
        
        USER REQUEST: "{input_text}"
        DETECTED VIBE: {vibe}
        GENRES: {genres}
        
        TOP RECOMMENDED TRACKS:
        {tracks_summary}
        
        Evaluate:
        1. How well do the top 3 tracks match the user's request?
        2. Do they align with the detected vibe and genres?
        3. Are there any surprising or irrelevant choices?
        
        Provide a JSON response with:
        {{
            "relevancy_score": 0-100,
            "reasoning": "explanation",
            "track_alignment": "explanation of how tracks match",
            "issues": ["list", "of", "issues"],
            "suggestions": ["list", "of", "improvements"]
        }}
        """
        
        try:
            response = model.generate_content(prompt)
            # Parse JSON from response
            text = response.text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except Exception as e:
            print(f"⚠️ Gemini error for prompt {prompt_data['prompt_num']}: {str(e)}")
        
        return {
            'relevancy_score': 0,
            'reasoning': f'Error: {str(e)}',
            'track_alignment': 'N/A',
            'issues': ['Analysis failed'],
            'suggestions': []
        }

    def analyze_accuracy(self, prompt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze accuracy of metadata and matching."""
        tracks = prompt_data.get('tracks', [])
        vibe = prompt_data.get('vibe', '')
        bpm_range = prompt_data.get('bpm_range', (0, 0))
        
        accuracy_checks = {
            'score_order_valid': all(
                tracks[i]['score'] >= tracks[i+1]['score'] 
                for i in range(len(tracks)-1)
            ) if len(tracks) > 1 else True,
            'score_ranges_valid': all(
                0 <= t['score'] <= 150 for t in tracks
            ),
            'track_count_matches': len(tracks) == prompt_data.get('limit', len(tracks)),
            'vibe_detected': bool(vibe and vibe != 'unknown'),
            'bpm_range_valid': bpm_range[0] > 0 and bpm_range[1] > bpm_range[0],
        }
        
        accuracy_score = (sum(accuracy_checks.values()) / len(accuracy_checks)) * 100
        
        return {
            'accuracy_score': accuracy_score,
            'checks': accuracy_checks,
            'issues': [k for k, v in accuracy_checks.items() if not v],
        }

    def analyze_all_prompts(self):
        """Analyze all prompts."""
        print(f"\n🔍 Analyzing {len(self.prompts_data)} prompts for relevancy and accuracy...")
        
        relevancy_scores = []
        accuracy_scores = []
        
        for idx, prompt_data in enumerate(self.prompts_data, 1):
            relevancy = self.analyze_relevancy(prompt_data)
            accuracy = self.analyze_accuracy(prompt_data)
            
            analysis_entry = {
                'prompt_num': prompt_data['prompt_num'],
                'input': prompt_data.get('input', ''),
                'vibe': prompt_data.get('vibe', ''),
                'relevancy': relevancy,
                'accuracy': accuracy,
                'timestamp': datetime.now().isoformat(),
            }
            
            self.analyses.append(analysis_entry)
            relevancy_scores.append(relevancy.get('relevancy_score', 0))
            accuracy_scores.append(accuracy.get('accuracy_score', 0))
            
            if idx % 100 == 0:
                print(f"  ✓ Analyzed {idx}/{len(self.prompts_data)} prompts...")
        
        # Calculate metrics
        self.metrics['total_prompts'] = len(self.analyses)
        
        if relevancy_scores:
            self.metrics['avg_relevancy_score'] = sum(relevancy_scores) / len(relevancy_scores)
            self.metrics['high_relevancy'] = sum(1 for s in relevancy_scores if s >= 80)
            self.metrics['medium_relevancy'] = sum(1 for s in relevancy_scores if 50 <= s < 80)
            self.metrics['low_relevancy'] = sum(1 for s in relevancy_scores if s < 50)
        
        if accuracy_scores:
            self.metrics['avg_accuracy_score'] = sum(accuracy_scores) / len(accuracy_scores)
            self.metrics['high_accuracy'] = sum(1 for s in accuracy_scores if s >= 80)
            self.metrics['medium_accuracy'] = sum(1 for s in accuracy_scores if 50 <= s < 80)
            self.metrics['low_accuracy'] = sum(1 for s in accuracy_scores if s < 50)
        
        print(f"✓ Analysis complete!")

    def generate_reports(self):
        """Generate analysis reports."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # JSON report
        json_file = Path(self.output_dir) / f"analysis_{timestamp}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'total_prompts_analyzed': self.metrics['total_prompts'],
                    'log_file': self.log_file,
                },
                'metrics': self.metrics,
                'analyses': self.analyses[:10],  # First 10 for brevity
                'note': 'Full analysis stored separately'
            }, f, indent=2, ensure_ascii=False)
        
        # CSV report
        csv_file = Path(self.output_dir) / f"analysis_{timestamp}.csv"
        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write("PromptNum,Input,Vibe,RelevancyScore,AccuracyScore,Issues\n")
            for analysis in self.analyses:
                relevancy_score = analysis['relevancy'].get('relevancy_score', 0)
                accuracy_score = analysis['accuracy'].get('accuracy_score', 0)
                issues = '|'.join(analysis['accuracy'].get('issues', []))
                input_text = analysis['input'].replace(',', ';').replace('"', '')
                f.write(f'{analysis["prompt_num"]},"{input_text}",{analysis["vibe"]},{relevancy_score},{accuracy_score},"{issues}"\n')
        
        # Summary report
        summary_file = Path(self.output_dir) / f"summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("VIBEFINDER AI — PROMPT-RESULT ANALYSIS REPORT\n")
            f.write("="*80 + "\n\n")
            
            f.write(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Log File: {self.log_file}\n")
            f.write(f"Total Prompts Analyzed: {self.metrics['total_prompts']}\n\n")
            
            f.write("RELEVANCY METRICS:\n")
            f.write(f"  Average Score: {self.metrics['avg_relevancy_score']:.1f}%\n")
            f.write(f"  High Relevancy (≥80%): {self.metrics['high_relevancy']} ({self.metrics['high_relevancy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n")
            f.write(f"  Medium Relevancy (50-79%): {self.metrics['medium_relevancy']} ({self.metrics['medium_relevancy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n")
            f.write(f"  Low Relevancy (<50%): {self.metrics['low_relevancy']} ({self.metrics['low_relevancy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n\n")
            
            f.write("ACCURACY METRICS:\n")
            f.write(f"  Average Score: {self.metrics['avg_accuracy_score']:.1f}%\n")
            f.write(f"  High Accuracy (≥80%): {self.metrics['high_accuracy']} ({self.metrics['high_accuracy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n")
            f.write(f"  Medium Accuracy (50-79%): {self.metrics['medium_accuracy']} ({self.metrics['medium_accuracy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n")
            f.write(f"  Low Accuracy (<50%): {self.metrics['low_accuracy']} ({self.metrics['low_accuracy']/max(self.metrics['total_prompts'],1)*100:.1f}%)\n\n")
            
            f.write("TOP ISSUES FOUND:\n")
            all_issues = {}
            for analysis in self.analyses:
                for issue in analysis['accuracy'].get('issues', []):
                    all_issues[issue] = all_issues.get(issue, 0) + 1
            
            sorted_issues = sorted(all_issues.items(), key=lambda x: x[1], reverse=True)
            for issue, count in sorted_issues[:10]:
                f.write(f"  • {issue}: {count} occurrences\n")
            
            f.write("\n" + "="*80 + "\n")
        
        print(f"\n📊 Reports generated:")
        print(f"  • {json_file}")
        print(f"  • {csv_file}")
        print(f"  • {summary_file}")
        
        return json_file, csv_file, summary_file

    def run(self):
        """Run the complete analysis pipeline."""
        print("="*80)
        print("VIBEFINDER AI — PROMPT-RESULT ANALYSIS ENGINE")
        print("="*80)
        
        self.parse_log_file()
        self.analyze_all_prompts()
        self.generate_reports()
        
        print("\n✅ Analysis complete!")


if __name__ == '__main__':
    log_file = 'qa_batch_v10k_3.log'
    analyzer = PromptResultAnalyzer(log_file)
    analyzer.run()
