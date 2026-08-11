import argparse
import pandas as pd
from src.visualization.chart_generator import ChartGenerator

def get_mock_data():
    """Provides sample data until the database module is ready."""
    trend_data = pd.DataFrame({
        'Date': pd.date_range(start='2023-10-01', periods=7).strftime('%Y-%m-%d'),
        'Present_Count': [45, 48, 42, 50, 46, 12, 49] 
    })
    
    class_data = pd.DataFrame({
        'Class': ['CS101', 'IT201', 'SE301', 'DS401'],
        'Attendance_Rate': [85, 92, 78, 88]
    })
    
    return trend_data, class_data

def main():
    parser = argparse.ArgumentParser(description="SAMS - Data Visualization Module")
    parser.add_argument('--trend', action='store_true', help='Generate attendance trend chart')
    parser.add_argument('--distribution', action='store_true', help='Generate class distribution chart')
    parser.add_argument('--all', action='store_true', help='Generate all visualization charts')
    args = parser.parse_args()

    print("--- Initializing SAMS Visualization Module ---")
    
    # Initialize the generator (points to the reports/charts directory)
    generator = ChartGenerator()
    
    # TODO: Replace get_mock_data() with calls to src.database.queries once ready
    trend_data, class_data = get_mock_data()

    # Determine which charts to run (default to 'all' if no flags provided)
    run_all = args.all or not any(vars(args).values())

    if args.trend or run_all:
        generator.generate_attendance_trend(trend_data)
        
    if args.distribution or run_all:
        generator.generate_class_distribution(class_data)
        
    print("--- Visualization Complete ---")

if __name__ == "__main__":
    main()