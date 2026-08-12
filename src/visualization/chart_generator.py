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

    def generate_student_summary(self, df, student_no, student_name=None,
                                 session_col='session', status_col='status',
                                 save=True):
        """Generates the per-student attendance summary required by the brief.

        Two panels side by side:
          * left  - one bar per session, coloured by present/absent, so the
                    pattern of attendance over the term is visible at a glance;
          * right - a donut of the totals with the attendance rate in the middle.

        Args:
            df: DataFrame with one row per session, holding ``session_col`` and
                ``status_col``. Rows are plotted in the order supplied.
            student_no: Student index, used in the title and the filename.
            student_name: Optional display name for the title.
            session_col: Column holding the session label.
            status_col: Column holding 'Present' or 'Absent'.
            save: Write the figure to ``output_dir`` when True.

        Returns:
            str | None: The saved file path, or None when nothing was plotted.
        """
        if df.empty:
            print(f"[Warning] No attendance records for {student_no}; nothing to plot.")
            return None

        present_mask = df[status_col].str.lower() == 'present'
        present_count = int(present_mask.sum())
        total = len(df)
        rate = present_count / total * 100 if total else 0.0

        # Present/absent carry a conventional meaning, so they use semantic
        # colours rather than the sequential report palette.
        present_colour, absent_colour = '#2a9d8f', '#e76f51'
        bar_colours = [present_colour if p else absent_colour for p in present_mask]

        fig, (ax_sessions, ax_total) = plt.subplots(
            1, 2, figsize=(13, 5.5), gridspec_kw={'width_ratios': [2, 1]})

        # --- Left: per-session attendance ---------------------------------
        ax_sessions.bar(df[session_col].astype(str), [1] * total, color=bar_colours)
        ax_sessions.set_title('Attendance by Session')
        ax_sessions.set_xlabel('Session')
        ax_sessions.set_ylim(0, 1.25)
        ax_sessions.set_yticks([])
        ax_sessions.tick_params(axis='x', rotation=45)
        ax_sessions.grid(False)

        for x, is_present in enumerate(present_mask):
            ax_sessions.text(x, 1.05, 'P' if is_present else 'A',
                             ha='center', va='bottom', fontweight='bold',
                             color=present_colour if is_present else absent_colour)

        # --- Right: overall rate ------------------------------------------
        absent_count = total - present_count
        wedge_sizes = [present_count, absent_count]
        wedge_colours = [present_colour, absent_colour]

        # A zero-sized wedge still draws an edge artefact, so drop empty slices.
        keep = [i for i, size in enumerate(wedge_sizes) if size > 0]
        ax_total.pie([wedge_sizes[i] for i in keep],
                     colors=[wedge_colours[i] for i in keep],
                     startangle=90,
                     wedgeprops={'width': 0.38, 'edgecolor': 'white'})
        ax_total.text(0, 0.08, f"{rate:.0f}%", ha='center', va='center',
                      fontsize=26, fontweight='bold')
        ax_total.text(0, -0.22, f"{present_count} of {total} present",
                      ha='center', va='center', fontsize=11)
        ax_total.set_title('Overall Attendance')

        heading = f"Attendance Summary - {student_no}"
        if student_name:
            heading += f" ({student_name})"
        fig.suptitle(heading, fontsize=16, fontweight='bold')
        fig.tight_layout()

        filepath = None
        if save:
            filepath = os.path.join(self.output_dir,
                                    f'attendance_summary_{student_no}.png')
            plt.savefig(filepath, dpi=300)
            print(f"[Success] Student summary saved to {filepath}")

        plt.close(fig)
        return filepath

    def generate_class_distribution(self, df, class_col='Class', rate_col='Attendance_Rate', save=True):
        """Generates a bar chart showing average attendance by class/department."""
        plt.figure()
        
        # Seaborn >=0.13 requires `hue` when a palette is supplied, and expects
        # the palette to hold exactly one colour per category.
        n_classes = df[class_col].nunique()
        sns.barplot(data=df, x=class_col, y=rate_col,
                    hue=class_col, palette=self.colors[:n_classes],
                    legend=False)
        
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