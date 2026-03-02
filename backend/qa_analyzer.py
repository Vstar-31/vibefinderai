#!/usr/bin/env python3
"""
QA ANALYZER FOR VIBEFINDER AI
Analyzes all prompt-result combinations for relevancy and accuracy
Generates comprehensive evaluation reports
"""

import re
import json
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

class PromptResult:
    """Represents a single prompt-result combination"""
    def __init__(self):
        self.prompt_num = 0
        self.input_text = ""
        self.language = ""
        self.knobs = {}
        self.limit = 0
        self.vibe = {"name": "", "confidence": 0}
        self.secondary_vibe = {"name": "", "confidence": 0}
        self.entity = {}
        self.tag_used = ""
        self.genres = []
        self.bpm_range = ""
        self.pool_size = ""
        self.tracks = []
        self.pro_mode = ""
        
    def to_dict(self):
        return {
            "prompt_num": self.prompt_num,
            "input": self.input_text,
            "language": self.language,
            "vibe": self.vibe,
            "secondary": self.secondary_vibe,
            "genres": self.genres,
            "tracks_count": len(self.tracks),
            "pro_mode": self.pro_mode
        }

class QAAnalyzer:
    """Main analyzer for QA batch results"""
    
    def __init__(self, log_file_path):
        self.log_file = log_file_path
        self.prompts = []
        self.analysis_results = []
        self.stats = {
            "total_prompts": 0,
            "total_tracks": 0,
            "high_relevancy": 0,
            "medium_relevancy": 0,
            "low_relevancy": 0,
            "accuracy_scores": [],
            "genres_distribution": defaultdict(int),
            "vibe_distribution": defaultdict(int),
            "score_patterns": defaultdict(int)
        }
        
    def parse_log_file(self, sample_size=None):
        """Parse the log file and extract prompt-result combinations"""
        print(f"[*] Parsing log file: {self.log_file}")
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            print(f"[!] Error reading log file: {e}")
            return False
            
        # Split by prompt markers
        prompt_blocks = re.split(r'--- \[PROMPT (\d+)/\d+\] ---', content)
        
        print(f"[*] Found {len(prompt_blocks)//2} prompts")
        
        count = 0
        for i in range(1, len(prompt_blocks), 2):
            if sample_size and count >= sample_size:
                break
                
            prompt_num = int(prompt_blocks[i])
            prompt_text = prompt_blocks[i+1]
            
            pr = self.parse_single_prompt(prompt_num, prompt_text)
            if pr:
                self.prompts.append(pr)
                count += 1
                
                if count % 100 == 0:
                    print(f"[*] Parsed {count} prompts...")
        
        self.stats["total_prompts"] = len(self.prompts)
        print(f"[✓] Successfully parsed {len(self.prompts)} prompts")
        return True
    
    def parse_single_prompt(self, num: int, text: str) -> Optional[PromptResult]:
        """Parse a single prompt block"""
        try:
            pr = PromptResult()
            pr.prompt_num = num
            
            # Extract INPUT
            input_match = re.search(r'INPUT\s*:\s*"([^"]+)"', text)
            if input_match:
                pr.input_text = input_match.group(1)
            
            # Extract LANGUAGE
            lang_match = re.search(r'LANGUAGE\s*:\s*(\w+)', text)
            if lang_match:
                pr.language = lang_match.group(1)
            
            # Extract LIMIT
            limit_match = re.search(r'LIMIT\s*:\s*(\d+)', text)
            if limit_match:
                pr.limit = int(limit_match.group(1))
            
            # Extract VIBE and confidence
            vibe_match = re.search(r'VIBE\s*:\s*(\w+)\s*\((\d+)%', text)
            if vibe_match:
                pr.vibe["name"] = vibe_match.group(1)
                pr.vibe["confidence"] = int(vibe_match.group(2))
            
            # Extract SECONDARY vibe
            sec_match = re.search(r'SECONDARY:\s*(\w+)\s*\((\d+)%', text)
            if sec_match:
                pr.secondary_vibe["name"] = sec_match.group(1)
                pr.secondary_vibe["confidence"] = int(sec_match.group(2))
            
            # Extract GENRES
            genres_match = re.search(r'GENRES\s*:\s*([^\\n]+)', text)
            if genres_match:
                genres_str = genres_match.group(1)
                pr.genres = [g.strip() for g in genres_str.split(',')]
            
            # Extract TAG_USED
            tag_match = re.search(r'TAG_USED\s*:\s*(\S+)', text)
            if tag_match:
                pr.tag_used = tag_match.group(1)
            
            # Extract BPM_RNG
            bpm_match = re.search(r'BPM_RNG\s*:\s*(\d+-\d+)', text)
            if bpm_match:
                pr.bpm_range = bpm_match.group(1)
            
            # Extract POOL_SZ
            pool_match = re.search(r'POOL_SZ\s*:\s*([^\\n]+)', text)
            if pool_match:
                pr.pool_size = pool_match.group(1)
            
            # Extract pro mode
            pro_match = re.search(r'PRO MODE\s*:\s*([^\\n]+)', text)
            if pro_match:
                pr.pro_mode = pro_match.group(1)
            
            # Extract TRACKS
            tracks_section = re.search(r'TRACKS.*?:\n(.*?)(?=🤖|---)', text, re.DOTALL)
            if tracks_section:
                tracks_text = tracks_section.group(1)
                track_lines = re.finditer(
                    r'\s*(\d+)\.\s*\[\s*([\d.]+)\]\s*([^—]+)—\s*(.+)$',
                    tracks_text,
                    re.MULTILINE
                )
                
                for match in track_lines:
                    track = {
                        "rank": int(match.group(1)),
                        "score": float(match.group(2)),
                        "name": match.group(3).strip(),
                        "artist": match.group(4).strip()
                    }
                    pr.tracks.append(track)
            
            return pr if pr.input_text else None
        except Exception as e:
            return None
    
    def analyze_relevancy(self, pr: PromptResult) -> Dict:
        """Analyze relevancy of tracks to the prompt"""
        analysis = {
            "prompt_num": pr.prompt_num,
            "input": pr.input_text,
            "vibe": pr.vibe["name"],
            "genres_requested": pr.genres[:5],  # Top 5
            "tracks_returned": len(pr.tracks),
            "relevancy_score": 0,
            "accuracy_score": 0,
            "issues": [],
            "observations": [],
            "score_distribution": [],
            "recommendations": []
        }
        
        if not pr.tracks:
            analysis["issues"].append("No tracks returned")
            analysis["relevancy_score"] = 0
            return analysis
        
        # Calculate score distribution
        scores = [t["score"] for t in pr.tracks]
        analysis["score_distribution"] = {
            "min": min(scores),
            "max": max(scores),
            "avg": sum(scores) / len(scores),
            "median": sorted(scores)[len(scores)//2] if scores else 0
        }
        
        # Check for relevancy based on vibe
        relevancy_keywords = {
            "chill": ["chill", "relax", "calm", "laid-back", "lo-fi", "downtempo"],
            "energetic": ["energy", "upbeat", "uptempo", "dance", "pump", "power"],
            "sad": ["sad", "dark", "melancholy", "depressing", "emotional", "cry"],
            "happy": ["happy", "bright", "uplifting", "cheerful", "joyful", "positive"],
            "calm": ["calm", "peace", "serene", "quiet", "smooth", "mellow"]
        }
        
        vibe_name = pr.vibe["name"].lower()
        input_text_lower = pr.input_text.lower()
        
        # Score relevancy based on indicator presence
        relevancy_check = 0
        
        if vibe_name in relevancy_keywords:
            keywords = relevancy_keywords[vibe_name]
            for keyword in keywords:
                if keyword in input_text_lower:
                    relevancy_check += 1
        
        # Check genres alignment (simple check)
        genre_match = 0
        for genre in pr.genres[:3]:
            if any(word in input_text_lower for word in genre.lower().split()):
                genre_match += 1
        
        # Calculate relevancy score (0-100)
        analysis["relevancy_score"] = min(100, (relevancy_check * 20) + (genre_match * 15) + 40)
        
        # Categorize
        if analysis["relevancy_score"] >= 75:
            analysis["category"] = "HIGH"
            self.stats["high_relevancy"] += 1
        elif analysis["relevancy_score"] >= 50:
            analysis["category"] = "MEDIUM"
            self.stats["medium_relevancy"] += 1
        else:
            analysis["category"] = "LOW"
            self.stats["low_relevancy"] += 1
        
        # Check for issues
        if len(pr.tracks) < pr.limit * 0.7:
            analysis["issues"].append(f"Low track yield: {len(pr.tracks)}/{pr.limit}")
        
        if scores[0] < scores[-1]:
            analysis["issues"].append("Score ordering appears inverted")
        
        # Check score variance
        score_variance = max(scores) - min(scores)
        if score_variance < 5:
            analysis["observations"].append("Low score variance indicates potential clustering issues")
        
        # Accuracy assessment
        if vibe_name and pr.vibe["confidence"] >= 50:
            analysis["accuracy_score"] = min(
                100,
                pr.vibe["confidence"] + (score_variance * 2)
            )
        else:
            analysis["accuracy_score"] = 50
        
        self.stats["accuracy_scores"].append(analysis["accuracy_score"])
        
        # Further observations
        if pr.pro_mode:
            analysis["observations"].append(f"Pro mode enabled: {pr.pro_mode}")
        
        if len(pr.tracks) > 0:
            top_track = pr.tracks[0]
            if top_track["score"] > 200:
                analysis["observations"].append(f"Extremely high top score ({top_track['score']})")
            elif top_track["score"] < 20:
                analysis["observations"].append(f"Low top score ({top_track['score']})")
        
        # Genre distribution
        for genre in pr.genres:
            self.stats["genres_distribution"][genre] += 1
        
        # Vibe distribution
        self.stats["vibe_distribution"][vibe_name] += 1
        
        self.stats["total_tracks"] += len(pr.tracks)
        
        return analysis
    
    def generate_report(self, output_file: str):
        """Generate comprehensive analysis report"""
        print("\n[*] Running relevancy and accuracy analysis...")
        
        for pr in self.prompts:
            analysis = self.analyze_relevancy(pr)
            self.analysis_results.append(analysis)
        
        print("[*] Generating report...")
        
        report_lines = []
        report_lines.append("=" * 100)
        report_lines.append("VIBEFINDER AI — QA ANALYSIS REPORT")
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 100)
        report_lines.append("")
        
        # Summary Statistics
        report_lines.append("📊 SUMMARY STATISTICS")
        report_lines.append("-" * 100)
        report_lines.append(f"Total Prompts Analyzed:        {self.stats['total_prompts']}")
        report_lines.append(f"Total Tracks Returned:         {self.stats['total_tracks']}")
        report_lines.append(f"Average Tracks per Prompt:     {self.stats['total_tracks'] / max(1, self.stats['total_prompts']):.1f}")
        report_lines.append("")
        
        # Relevancy Breakdown
        report_lines.append("🎯 RELEVANCY BREAKDOWN")
        report_lines.append("-" * 100)
        total = self.stats["total_prompts"]
        high_pct = (self.stats["high_relevancy"] / total * 100) if total > 0 else 0
        med_pct = (self.stats["medium_relevancy"] / total * 100) if total > 0 else 0
        low_pct = (self.stats["low_relevancy"] / total * 100) if total > 0 else 0
        
        report_lines.append(f"HIGH Relevancy:                {self.stats['high_relevancy']:4d} ({high_pct:5.1f}%)")
        report_lines.append(f"MEDIUM Relevancy:              {self.stats['medium_relevancy']:4d} ({med_pct:5.1f}%)")
        report_lines.append(f"LOW Relevancy:                 {self.stats['low_relevancy']:4d} ({low_pct:5.1f}%)")
        report_lines.append("")
        
        # Accuracy Metrics
        if self.stats["accuracy_scores"]:
            avg_accuracy = sum(self.stats["accuracy_scores"]) / len(self.stats["accuracy_scores"])
            max_accuracy = max(self.stats["accuracy_scores"])
            min_accuracy = min(self.stats["accuracy_scores"])
            report_lines.append("✅ ACCURACY METRICS")
            report_lines.append("-" * 100)
            report_lines.append(f"Average Accuracy Score:        {avg_accuracy:.1f}/100")
            report_lines.append(f"Max Accuracy Score:            {max_accuracy:.1f}/100")
            report_lines.append(f"Min Accuracy Score:            {min_accuracy:.1f}/100")
            report_lines.append("")
        
        # Top Genres
        if self.stats["genres_distribution"]:
            report_lines.append("🎵 TOP GENRES USED")
            report_lines.append("-" * 100)
            sorted_genres = sorted(
                self.stats["genres_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:15]
            for genre, count in sorted_genres:
                pct = (count / sum(self.stats["genres_distribution"].values())) * 100
                report_lines.append(f"  {genre:30s}  {count:5d} ({pct:5.1f}%)")
            report_lines.append("")
        
        # Vibe Distribution
        if self.stats["vibe_distribution"]:
            report_lines.append("😊 VIBE DISTRIBUTION")
            report_lines.append("-" * 100)
            sorted_vibes = sorted(
                self.stats["vibe_distribution"].items(),
                key=lambda x: x[1],
                reverse=True
            )
            for vibe, count in sorted_vibes:
                pct = (count / sum(self.stats["vibe_distribution"].values())) * 100
                report_lines.append(f"  {vibe:20s}  {count:5d} ({pct:5.1f}%)")
            report_lines.append("")
        
        # Detailed Analysis (sample first 50)
        report_lines.append("=" * 100)
        report_lines.append("DETAILED ANALYSIS (First 50 Prompts)")
        report_lines.append("=" * 100)
        report_lines.append("")
        
        for i, analysis in enumerate(self.analysis_results[:50], 1):
            report_lines.append(f"[{i:03d}] PROMPT #{analysis['prompt_num']}")
            report_lines.append(f"      Input: {analysis['input'][:70]}{'...' if len(analysis['input']) > 70 else ''}")
            report_lines.append(f"      Vibe: {analysis['vibe']} | Relevancy: {analysis['relevancy_score']:.0f}/100 | Category: {analysis['category']}")
            report_lines.append(f"      Tracks: {analysis['tracks_returned']} | Accuracy: {analysis['accuracy_score']:.0f}/100")
            
            if analysis["score_distribution"]:
                dist = analysis["score_distribution"]
                report_lines.append(f"      Score Range: {dist['min']:.1f} - {dist['max']:.1f} (avg: {dist['avg']:.1f})")
            
            if analysis["issues"]:
                for issue in analysis["issues"]:
                    report_lines.append(f"      ⚠️  ISSUE: {issue}")
            
            if analysis["observations"]:
                for obs in analysis["observations"]:
                    report_lines.append(f"      📝 {obs}")
            
            report_lines.append("")
        
        # Write report
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(report_lines))
            
            print(f"[✓] Report saved to: {output_file}")
            print(f"[✓] Total lines in report: {len(report_lines)}")
            
        except Exception as e:
            print(f"[!] Error writing report: {e}")
            return False
        
        # Also save JSON for programmatic access
        json_file = output_file.replace('.txt', '.json')
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json_data = {
                    "generated_at": datetime.now().isoformat(),
                    "statistics": {
                        "total_prompts": self.stats["total_prompts"],
                        "total_tracks": self.stats["total_tracks"],
                        "high_relevancy": self.stats["high_relevancy"],
                        "medium_relevancy": self.stats["medium_relevancy"],
                        "low_relevancy": self.stats["low_relevancy"],
                        "avg_accuracy": sum(self.stats["accuracy_scores"]) / len(self.stats["accuracy_scores"]) if self.stats["accuracy_scores"] else 0
                    },
                    "detailed_results": self.analysis_results[:50]
                }
                json.dump(json_data, f, indent=2)
            
            print(f"[✓] JSON data saved to: {json_file}")
            
        except Exception as e:
            print(f"[!] Error writing JSON: {e}")
        
        return True

def main():
    """Main entry point"""
    import sys
    
    log_path = r"g:\my projects\vibefinderai\vibefinderai\backend\qa_batch_v10k_3.log"
    output_path = r"g:\my projects\vibefinderai\vibefinderai\backend\qa_analysis_report.txt"
    
    analyzer = QAAnalyzer(log_path)
    
    # Parse log (full dataset)
    if not analyzer.parse_log_file():
        print("[!] Failed to parse log file")
        sys.exit(1)
    
    # Generate report
    if not analyzer.generate_report(output_path):
        print("[!] Failed to generate report")
        sys.exit(1)
    
    print("\n[✓] Analysis complete!")

if __name__ == "__main__":
    main()
