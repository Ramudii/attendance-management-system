
"""
Student Attendance Visualization
Author: Ashen KGP - Data Visualization
"""

import argparse
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from database.database_manager import DatabaseManager
from src.logger import setup_logger

class AttendanceVisualizer:
    """Visualize attendance data with multiple chart types"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.logger = setup_logger('visualizer')
        
        # Set style
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (12, 6)
        plt.rcParams['font.size'] = 12
        
        # Color schemes
        self.colors = {
            'present': '#2ecc71',
            'absent': '#e74c3c',
            'primary': '#3498db',
            'secondary': '#9b59b6'
        }
        
        self.logger.info("Attendance Visualizer initialized")
    
    def get_student_attendance_data(self, student_no):
        """
        Get attendance data for student
        
        Args:
            student_no: Student number
            
        Returns:
            dict: Student attendance data
        """
        student = self.db.get_student(student_no)
        
        if not student:
            self.logger.error(f"Student {student_no} not found")
            return None
        
        attendance = self.db.get_student_attendance(student_no)
        summary = self.db.get_attendance_summary(student_no)
        
        return {
            'student': student,
            'attendance': attendance,
            'summary': summary
        }
    
    def create_bar_chart(self, data, student_no, save_path=None):
        """
        Create bar chart for attendance
        
        Args:
            data: Student attendance data
            student_no: Student number
            save_path: Path to save chart
            
        Returns:
            matplotlib.figure.Figure: Created figure
        """
        if data['attendance'].empty:
            self.logger.warning(f"No attendance records for student {student_no}")
            return None
        
        df = data['attendance']
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 6))
        
        # Prepare data
        dates = df['lecture_date'].tolist()
        statuses = df['status'].tolist()
        
        # Color mapping
        colors = [self.colors['present'] if s == 'Present' else self.colors['absent'] 
                 for s in statuses]
        
        # Create bars
        bars = ax.bar(dates, [1 if s == 'Present' else 0 for s in statuses], 
                      color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)
        
        # Customize
        ax.set_xlabel('Lecture Date', fontsize=12)
        ax.set_ylabel('Attendance Status', fontsize=12)
        ax.set_title(f'Attendance for {data["student"]["name"]} ({student_no})', 
                     fontsize=14, fontweight='bold')
        
        # Set y-axis
        ax.set_ylim([-0.5, 1.5])
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Absent', 'Present'])
        
        # Rotate x-axis labels
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add value labels on bars
        for i, bar in enumerate(bars):
            height = bar.get_height()
            status = statuses[i]
            label = '✓' if status == 'Present' else '✗'
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   label, ha='center', va='bottom', fontsize=12)
        
        # Add grid
        ax.grid(True, alpha=0.3, axis='y')
        
        # Add legend
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=self.colors['present'], label='Present'),
            Patch(facecolor=self.colors['absent'], label='Absent')
        ]
        ax.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        
        # Save if path provided
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Bar chart saved to {save_path}")
        
        return fig
    
    def create_pie_chart(self, summary, student_no, save_path=None):
        """
        Create pie chart for attendance summary
        
        Args:
            summary: Attendance summary
            student_no: Student number
            save_path: Path to save chart
            
        Returns:
            matplotlib.figure.Figure: Created figure
        """
        fig, ax = plt.subplots(figsize=(8, 8))
        
        sizes = [summary['present'], summary['absent']]
        labels = ['Present', 'Absent']
        colors = [self.colors['present'], self.colors['absent']]
        explode = (0.05, 0.05)
        
        # Create pie chart
        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', startangle=90, shadow=True
        )
        
        # Style
        for text in texts:
            text.set_fontsize(12)
        for autotext in autotexts:
            autotext.set_fontsize(14)
            autotext.set_weight('bold')
        
        ax.set_title(f'Attendance Summary\nRate: {summary["attendance_rate"]:.1f}%', 
                     fontsize=14, fontweight='bold')
        
        # Add total information
        total = summary['present'] + summary['absent']
        ax.text(0, -1.2, f'Total Lectures: {total}', 
                ha='center', fontsize=12)
        
        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Pie chart saved to {save_path}")
        
        return fig
    
    def create_line_chart(self, data, student_no, save_path=None):
        """
        Create line chart for attendance trends
        
        Args:
            data: Student attendance data
            student_no: Student number
            save_path: Path to save chart
            
        Returns:
            matplotlib.figure.Figure: Created figure
        """
        if data['attendance'].empty:
            return None
        
        df = data['attendance'].copy()
        
        # Convert status to numeric
        df['present_numeric'] = df['status'].apply(lambda x: 1 if x == 'Present' else 0)
        
        # Calculate cumulative attendance rate
        df['cumulative_present'] = df['present_numeric'].cumsum()
        df['day_number'] = range(1, len(df) + 1)
        df['cumulative_rate'] = (df['cumulative_present'] / df['day_number']) * 100
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Subplot 1: Daily attendance
        ax1.plot(df['lecture_date'], df['present_numeric'], 
                marker='o', linewidth=2, markersize=8, color=self.colors['primary'])
        ax1.set_xlabel('Lecture Date')
        ax1.set_ylabel('Attendance')
        ax1.set_title('Daily Attendance', fontsize=12, fontweight='bold')
        ax1.set_ylim([-0.2, 1.2])
        ax1.set_yticks([0, 1])
        ax1.set_yticklabels(['Absent', 'Present'])
        ax1.grid(True, alpha=0.3)
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Subplot 2: Cumulative attendance rate
        ax2.plot(df['lecture_date'], df['cumulative_rate'], 
                marker='s', linewidth=2, markersize=8, color=self.colors['secondary'])
        ax2.set_xlabel('Lecture Date')
        ax2.set_ylabel('Cumulative Attendance Rate (%)')
        ax2.set_title('Cumulative Attendance Rate', fontsize=12, fontweight='bold')
        ax2.set_ylim([0, 105])
        ax2.grid(True, alpha=0.3)
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha='right')
        
        # Add horizontal line at 80%
        ax2.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='80% Threshold')
        ax2.legend()
        
        plt.suptitle(f'Attendance Trends - {data["student"]["name"]} ({student_no})', 
                     fontsize=14, fontweight='bold')
        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            self.logger.info(f"Line chart saved to {save_path}")
        
        return fig
    
    def create_dashboard(self, student_no, save_dir='reports/charts'):
        """
        Create a complete dashboard for a student
        
        Args:
            student_no: Student number
            save_dir: Directory to save charts
        """
        # Get data
        data = self.get_student_attendance_data(student_no)
        if data is None:
            print(f"❌ Student {student_no} not found")
            return
        
        # Create save directory
        os.makedirs(save_dir, exist_ok=True)
        
        # Display summary
        print("\n" + "="*60)
        print(f"📊 ATTENDANCE REPORT - {data['student']['name']}")
        print("="*60)
        print(f"Student Number: {student_no}")
        print(f"Total Lectures: {data['summary']['total_days']}")
        print(f"Present: {data['summary']['present']} ✅")
        print(f"Absent: {data['summary']['absent']} ❌")
        print(f"Attendance Rate: {data['summary']['attendance_rate']:.1f}%")
        print("="*60)
        
        # Create charts
        fig1 = self.create_bar_chart(
            data, student_no, 
            f'{save_dir}/bar_chart_{student_no}.png'
        )
        
        fig2 = self.create_pie_chart(
            data['summary'], student_no,
            f'{save_dir}/pie_chart_{student_no}.png'
        )
        
        fig3 = self.create_line_chart(
            data, student_no,
            f'{save_dir}/line_chart_{student_no}.png'
        )
        
        # Show charts
        if fig1:
            plt.figure(fig1.number)
            plt.show()
        if fig2:
            plt.figure(fig2.number)
            plt.show()
        if fig3:
            plt.figure(fig3.number)
            plt.show()
        
        print(f"\n📁 Charts saved to: {save_dir}")

def main():
    parser = argparse.ArgumentParser(
        description='Student Attendance Visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python infovis.py 10000409
  python infovis.py --output reports/ 10000409
        """
    )
    
    parser.add_argument('student_no', help='Student number to visualize')
    parser.add_argument('--output', '-o', default='reports/charts',
                       help='Output directory for charts (default: reports/charts)')
    
    args = parser.parse_args()
    
    # Create visualizer and display
    visualizer = AttendanceVisualizer()
    visualizer.create_dashboard(args.student_no, args.output)

if __name__ == "__main__":
    main()