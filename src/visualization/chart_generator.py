import os
import matplotlib.pyplot as plt

from .style_manager import StyleManager


class ChartGenerator:
    """Builds bar, pie, and line charts for student attendance"""

    def __init__(self, style_manager=None, logger=None):
        self.style = style_manager if style_manager else StyleManager()
        self.style.apply_global_style()
        self.logger = logger

    def _log(self, level, message):
        if self.logger:
            getattr(self.logger, level)(message)

    def _save(self, fig, save_path):
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches='tight')
            self._log('info', f"Chart saved to {save_path}")

    def create_bar_chart(self, attendance_df, student_name, student_no, save_path=None):
        """
        Bar chart of Present/Absent per lecture date.

        Args:
            attendance_df: DataFrame with columns ['lecture_date', 'status']
            student_name: str
            student_no: str
            save_path: optional file path to save PNG
        """
        if attendance_df is None or attendance_df.empty:
            self._log('warning', f"No attendance records for student {student_no}")
            return None

        dates = attendance_df['lecture_date'].tolist()
        statuses = attendance_df['status'].tolist()
        colors = self.style.status_colors(statuses)

        fig, ax = plt.subplots(figsize=(14, 6))
        bars = ax.bar(dates, [1 if s == 'Present' else 0 for s in statuses],
                       color=colors, alpha=0.7, edgecolor='black', linewidth=0.5)

        ax.set_xlabel('Lecture Date', fontsize=12)
        ax.set_ylabel('Attendance Status', fontsize=12)
        self.style.style_title(ax, f'Attendance for {student_name} ({student_no})')

        ax.set_ylim([-0.5, 1.5])
        ax.set_yticks([0, 1])
        ax.set_yticklabels(['Absent', 'Present'])

        self.style.rotate_x_labels(ax)

        for i, bar in enumerate(bars):
            height = bar.get_height()
            label = '✓' if statuses[i] == 'Present' else '✗'
            ax.text(bar.get_x() + bar.get_width() / 2., height,
                    label, ha='center', va='bottom', fontsize=12)

        self.style.apply_grid(ax)
        ax.legend(handles=self.style.legend_patches(), loc='upper right')

        plt.tight_layout()
        self._save(fig, save_path)
        return fig

    def create_pie_chart(self, summary, student_no, save_path=None):
        """
        Pie chart of overall Present vs Absent split.

        Args:
            summary: dict with keys 'present', 'absent', 'attendance_rate'
            student_no: str
            save_path: optional file path to save PNG
        """
        fig, ax = plt.subplots(figsize=(8, 8))

        sizes = [summary['present'], summary['absent']]
        labels = ['Present', 'Absent']
        colors = [self.style.colors['present'], self.style.colors['absent']]
        explode = (0.05, 0.05)

        wedges, texts, autotexts = ax.pie(
            sizes, explode=explode, labels=labels, colors=colors,
            autopct='%1.1f%%', startangle=90, shadow=True
        )

        for text in texts:
            text.set_fontsize(12)
        for autotext in autotexts:
            autotext.set_fontsize(14)
            autotext.set_weight('bold')

        self.style.style_title(ax, f'Attendance Summary\nRate: {summary["attendance_rate"]:.1f}%')

        total = summary['present'] + summary['absent']
        ax.text(0, -1.2, f'Total Lectures: {total}', ha='center', fontsize=12)

        plt.tight_layout()
        self._save(fig, save_path)
        return fig

    def create_line_chart(self, attendance_df, student_name, student_no, save_path=None):
        """
        Two-panel line chart: daily attendance + cumulative attendance rate.

        Args:
            attendance_df: DataFrame with columns ['lecture_date', 'status']
            student_name: str
            student_no: str
            save_path: optional file path to save PNG
        """
        if attendance_df is None or attendance_df.empty:
            self._log('warning', f"No attendance records for student {student_no}")
            return None

        df = attendance_df.copy()
        df['present_numeric'] = df['status'].apply(lambda x: 1 if x == 'Present' else 0)
        df['cumulative_present'] = df['present_numeric'].cumsum()
        df['day_number'] = range(1, len(df) + 1)
        df['cumulative_rate'] = (df['cumulative_present'] / df['day_number']) * 100

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Daily attendance
        ax1.plot(df['lecture_date'], df['present_numeric'],
                 marker='o', linewidth=2, markersize=8, color=self.style.colors['primary'])
        ax1.set_xlabel('Lecture Date')
        ax1.set_ylabel('Attendance')
        self.style.style_title(ax1, 'Daily Attendance', fontsize=12)
        ax1.set_ylim([-0.2, 1.2])
        ax1.set_yticks([0, 1])
        ax1.set_yticklabels(['Absent', 'Present'])
        self.style.apply_grid(ax1, axis='both')
        self.style.rotate_x_labels(ax1)

        # Cumulative attendance rate
        ax2.plot(df['lecture_date'], df['cumulative_rate'],
                 marker='s', linewidth=2, markersize=8, color=self.style.colors['secondary'])
        ax2.set_xlabel('Lecture Date')
        ax2.set_ylabel('Cumulative Attendance Rate (%)')
        self.style.style_title(ax2, 'Cumulative Attendance Rate', fontsize=12)
        ax2.set_ylim([0, 105])
        self.style.apply_grid(ax2, axis='both')
        self.style.rotate_x_labels(ax2)
        ax2.axhline(y=80, color='red', linestyle='--', alpha=0.5, label='80% Threshold')
        ax2.legend()

        plt.suptitle(f'Attendance Trends - {student_name} ({student_no})',
                     fontsize=14, fontweight='bold')
        plt.tight_layout()
        self._save(fig, save_path)
        return fig