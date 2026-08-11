import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from .style_manager import StyleManager

class ChartGenerator:
    """Handles the creation and saving of attendance visualizations."""
    
    def __init__(self, output_dir="reports/charts"):
        self.output_dir = output_dir
        # Ensure the output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Apply global styles
        StyleManager.setup_theme()
        self.colors = StyleManager.get_color_palette()

    def generate_attendance_trend(self, df, date_col='Date', count_col='Present_Count', save=True):
        """Generates a line chart showing attendance trends over time."""
        plt.figure()
        
        sns.lineplot(data=df, x=date_col, y=count_col, marker='o', color=self.colors[2])
        
        plt.title('Daily Attendance Trend')
        plt.xlabel('Date')
        plt.ylabel('Number of Students Present')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        if save:
            filepath = os.path.join(self.output_dir, 'attendance_trend.png')
            plt.savefig(filepath, dpi=300)
            print(f"[Success] Trend chart saved to {filepath}")
            
        plt.close()

    def generate_class_distribution(self, df, class_col='Class', rate_col='Attendance_Rate', save=True):
        """Generates a bar chart showing average attendance by class/department."""
        plt.figure()
        
        sns.barplot(data=df, x=class_col, y=rate_col, palette=self.colors)
        
        plt.title('Average Attendance Rate by Class')
        plt.xlabel('Class/Module')
        plt.ylabel('Attendance Rate (%)')
        plt.ylim(0, 100) # Percentages max out at 100
        plt.tight_layout()
        
        if save:
            filepath = os.path.join(self.output_dir, 'class_distribution.png')
            plt.savefig(filepath, dpi=300)
            print(f"[Success] Distribution chart saved to {filepath}")
            
        plt.close()