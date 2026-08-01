import matplotlib.pyplot as plt
import seaborn as sns


class StyleManager:
    """Centralizes styling/theme settings for attendance charts"""

    # Default color palette used across all chart types
    DEFAULT_COLORS = {
        'present': '#2ecc71',
        'absent': '#e74c3c',
        'primary': '#3498db',
        'secondary': '#9b59b6',
        'warning': '#f39c12',
        'neutral': '#95a5a6',
    }

    def __init__(self, theme='whitegrid', colors=None, base_font_size=12):
        """
        Args:
            theme: seaborn style theme (e.g. 'whitegrid', 'darkgrid')
            colors: optional dict overriding default color scheme
            base_font_size: default font size applied globally
        """
        self.theme = theme
        self.colors = colors if colors else dict(self.DEFAULT_COLORS)
        self.base_font_size = base_font_size

    def apply_global_style(self, figsize=(12, 6)):
        """Apply seaborn/matplotlib global style settings"""
        sns.set_style(self.theme)
        plt.rcParams['figure.figsize'] = figsize
        plt.rcParams['font.size'] = self.base_font_size

    def status_color(self, status):
        """Return the color associated with an attendance status string"""
        return self.colors['present'] if status == 'Present' else self.colors['absent']

    def status_colors(self, statuses):
        """Map a list of status strings to their corresponding colors"""
        return [self.status_color(s) for s in statuses]

    def legend_patches(self):
        """Return standard Present/Absent legend patches for bar/pie charts"""
        from matplotlib.patches import Patch
        return [
            Patch(facecolor=self.colors['present'], label='Present'),
            Patch(facecolor=self.colors['absent'], label='Absent'),
        ]

    def style_title(self, ax, text, fontsize=14):
        ax.set_title(text, fontsize=fontsize, fontweight='bold')

    def rotate_x_labels(self, ax, rotation=45):
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=rotation, ha='right')

    def apply_grid(self, ax, alpha=0.3, axis='y'):
        ax.grid(True, alpha=alpha, axis=axis)