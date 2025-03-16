# CommiTiq Impact Score Analysis

This directory contains tools for analyzing GitHub user data stored in a PostgreSQL database to validate and optimize the thresholds, constants, and weights used in the CommiTiq impact score calculation algorithm.

## Directory Structure

```
analysis/
├── logs/                  # Log files from analysis runs
├── notebooks/             # Jupyter notebooks for interactive analysis
├── results/               # Analysis results and visualizations
├── scripts/               # Python modules for data analysis
│   ├── db_connection.py   # Database connection module
│   └── threshold_analyzer.py # Analysis logic
├── requirements.txt       # Python dependencies
├── run_analysis.py        # Main script to run analysis
└── README.md              # This file
```

## Setup

### Prerequisites

- Python 3.8 or later
- PostgreSQL database containing GitHub user data
- `.env` file with database credentials in the project root

### Installation

1. Create a virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Ensure your `.env` file contains the following variables:

```
DB_HOST=your_postgresql_host
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_PORT=5432  # Default PostgreSQL port
```

## Running the Analysis

### Using the Python Script

Run the main analysis script:

```bash
python run_analysis.py
```

This will:
1. Connect to the database using credentials from `.env`
2. Load the necessary data
3. Analyze distributions, weights, and factors
4. Generate optimized recommendations
5. Save results to the `results/` directory

### Using the Jupyter Notebook

For interactive analysis and visualization:

1. Start Jupyter:

```bash
jupyter notebook
```

2. Open `notebooks/threshold_optimization.ipynb`
3. Run the cells to perform analysis and visualize the data

## Analysis Components

The analysis covers the following aspects of the impact score calculation:

1. **Normalization Thresholds**: Determines appropriate min/max values for percentile-based normalization of metrics like pulls, commits, reviews, etc.

2. **Impact Score Weights**: Analyzes the importance of different metrics in determining the final impact score.

3. **Repository Impact Factors**: Evaluates the balance between technical impact and ecosystem impact.

4. **Contribution Ratio Exponent**: Determines the optimal exponent for diminishing returns on higher contribution percentages.

5. **Collaboration Factor Parameters**: Optimizes the parameters used in the collaboration factor calculation.

6. **Review Activity Normalization**: Analyzes the normalization factor for review comments.

## Results

Analysis results are saved to the `results/` directory, including:

- JSON file with recommended thresholds and constants
- Visualization plots showing distributions and comparisons
- Detailed logs of the analysis process

## How to Use the Results

After running the analysis, you can:

1. Review the recommended thresholds and constants in the JSON file
2. Compare them with the current values used in the codebase
3. Update the constants in the backend code if necessary

The recommended values are derived from statistical analysis of real GitHub user data and should provide a more accurate impact score calculation.

## Extending the Analysis

To extend or modify the analysis:

1. Update the SQL queries in `db_connection.py` if needed
2. Add or modify analysis methods in `threshold_analyzer.py`
3. Create additional visualizations in the Jupyter notebook 