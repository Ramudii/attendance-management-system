import matplotlib.pyplot as plt
import seaborn as sns

class StyleManager:
    """Manages the visual styling and themes for all project charts."""
    
    @staticmethod
    def setup_theme():
        """Configures the global visual theme."""
        sns.set_theme(style="whitegrid")
        plt.rcParams.update({
            'figure.figsize': (10, 6),
            'axes.titlesize': 16,
            'axes.titleweight': 'bold',
            'axes.labelsize': 12,
            'xtick.labelsize': 10,
            'ytick.labelsize': 10,
            'font.family': 'sans-serif',
            'lines.linewidth': 2.5
        })
        
    @staticmethod
    def get_color_palette():
        """Returns the standard color palette for the system."""
        # Using a professional palette suitable for reports
        return sns.color_palette("crest", 8)