import re
import matplotlib.pyplot as plt
import os
import sys

def parse_ycsb_output(filepath):
    """Parses YCSB output file to extract overall throughput and latency metrics."""
    metrics = {
        'OVERALL': {'RunTime(ms)': None, 'Throughput(ops/sec)': None},
        'UPDATE': {'Operations': None, 'AverageLatency(us)': None, 'MinLatency(us)': None,
                     'MaxLatency(us)': None, '95thPercentileLatency(us)': None, '99thPercentileLatency(us)': None,
                     'Return=OK': None, 'LatencyDistribution': []},
        'READ': {'Operations': None, 'AverageLatency(us)': None, 'MinLatency(us)': None,
                   'MaxLatency(us)': None, '95thPercentileLatency(us)': None, '99thPercentileLatency(us)': None,
                   'Return=OK': None, 'LatencyDistribution': []}
    }
    current_section = None
    latency_data = []

    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('[OVERALL]'):
                    parts = line.split(', ')
                    if len(parts) == 3:
                        metrics['OVERALL']['RunTime(ms)'] = float(parts[1])
                        metrics['OVERALL']['Throughput(ops/sec)'] = float(parts[2])
                elif line.startswith('[UPDATE]') or line.startswith('[READ]'):
                    current_section = line.split(', ')[0][1:-1] # Extracts UPDATE or READ
                    parts = line.split(', ')
                    if len(parts) >= 3:
                        metrics[current_section][parts[1]] = float(parts[2])
                elif current_section and (line.startswith('0,') or line.startswith('>1000') or (line and line[0].isdigit() and ',' in line)):
                    if current_section in ['UPDATE', 'READ']:
                        try:
                            latency_value, count = map(int, line.split(','))
                            metrics[current_section]['LatencyDistribution'].append((latency_value, count))
                        except ValueError:
                            # Handle cases like >1000,0 or other non-integer lines if necessary
                            pass
    except FileNotFoundError:
        print(f"Warning: File not found {filepath}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Warning: Error parsing {filepath}: {e}", file=sys.stderr)
        return None
    return metrics

def get_latency_values(latency_distribution):
    """Converts latency distribution into a list of individual latency values."""
    latencies = []
    for latency, count in latency_distribution:
        latencies.extend([latency] * count)
    return latencies

def generate_plot(all_metrics, output_image_path):
    """Generates a box-and-whiskers plot for UPDATE latencies."""
    labels = []
    data_to_plot = []

    for db_name, metrics_data in all_metrics.items():
        if metrics_data and metrics_data['UPDATE']['Operations'] and metrics_data['UPDATE']['LatencyDistribution']:
            update_latencies = get_latency_values(metrics_data['UPDATE']['LatencyDistribution'])
            if update_latencies: # Ensure there's data to plot
                labels.append(db_name)
                data_to_plot.append(update_latencies)

    if not data_to_plot:
        print("No UPDATE latency data available to generate plot.", file=sys.stderr)
        # Create an empty plot or a plot with a message
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No UPDATE latency data available for plotting.",
                horizontalalignment='center', verticalalignment='center', transform=ax.transAxes)
        plt.savefig(output_image_path)
        plt.close()
        return

    plt.figure(figsize=(12, 8))
    plt.boxplot(data_to_plot, labels=labels, showfliers=False) # showfliers=False to hide outliers for better readability
    plt.title('YCSB Workload A - UPDATE Latency Comparison')
    plt.ylabel('Latency (us)')
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(output_image_path)
    plt.close()
    print(f"Plot generated: {output_image_path}")

def generate_markdown_report(all_metrics, plot_image_path, output_md_path):
    """Generates a Markdown report summarizing benchmark results."""
    with open(output_md_path, 'w') as md_file:
        md_file.write("# YCSB Benchmark Comparison Report\n\n")
        md_file.write("This report summarizes the YCSB Workload A results for various databases.\n\n")

        md_file.write("## Overall Performance Summary\n\n")
        md_file.write("| Database         | Overall Throughput (ops/sec) | UPDATE Avg Latency (us) | READ Avg Latency (us) |\n")
        md_file.write("|------------------|------------------------------|-------------------------|-----------------------|\n")

        for db_name, metrics_data in sorted(all_metrics.items()):
            if metrics_data:
                throughput = metrics_data['OVERALL'].get('Throughput(ops/sec)', 'N/A')
                update_avg_latency = metrics_data['UPDATE'].get('AverageLatency(us)', 'N/A')
                read_avg_latency = metrics_data['READ'].get('AverageLatency(us)', 'N/A')
                md_file.write(f"| {db_name:<16} | {throughput:<28} | {update_avg_latency:<23} | {read_avg_latency:<21} |\n")
            else:
                md_file.write(f"| {db_name:<16} | N/A                          | N/A                     | N/A                   |\n")
        md_file.write("\n")

        md_file.write("## UPDATE Latency Distribution\n\n")
        if os.path.exists(plot_image_path):
            md_file.write(f"![UPDATE Latency Box Plot]({os.path.basename(plot_image_path)})\n\n")
            md_file.write(f"*The box plot above shows the distribution of UPDATE latencies (in microseconds). Outliers are not shown for clarity.*\n")
        else:
            md_file.write("Latency plot could not be generated.\n")

        md_file.write("\n## Notes\n")
        md_file.write("- **Workload**: YCSB Workload A (50% Read, 50% Update).\n")
        md_file.write("- **Latency Data**: The box plot visualizes the 0-1000us range primarily. For detailed percentile data beyond what YCSB typically outputs by default (e.g., for precise 25th, 50th, 75th percentiles needed for traditional box plots), YCSB may need specific configuration (`measurementtype=hdrhistogram` or `timeseries`) and post-processing of its raw output.\n")
        md_file.write("- **FoundationDB**: Results for FoundationDB are from its specific YCSB binding, which might report metrics differently than the JDBC binding used for others.\n")

    print(f"Markdown report generated: {output_md_path}")

if __name__ == "__main__":
    base_path = '.' # Assumes script is run from the root of the artifact download directory
    db_results_files = {
        "PostgreSQL": os.path.join(base_path, "postgresql_results.txt"),
        "CockroachDB": os.path.join(base_path, "cockroachdb_results.txt"),
        "FoundationDB": os.path.join(base_path, "foundationdb_results.txt"),
        "SQLite": os.path.join(base_path, "sqlite_results.txt"),
        "DuckDB": os.path.join(base_path, "duckdb_results.txt")
    }

    all_db_metrics = {}
    for db, filepath in db_results_files.items():
        print(f"Processing {filepath} for {db}...")
        metrics = parse_ycsb_output(filepath)
        all_db_metrics[db] = metrics

    plot_file = "latency_comparison_plot.png"
    report_file = "benchmark_report.md"

    generate_plot(all_db_metrics, plot_file)
    generate_markdown_report(all_db_metrics, plot_file, report_file)

    # Output for GitHub Actions
    print(f"::set-output name=report_file::{report_file}")
    print(f"::set-output name=plot_file::{plot_file}")