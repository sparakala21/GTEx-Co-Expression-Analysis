import networkx as nx
import argparse
import signal
import sys
from multiprocessing import Pool, cpu_count
from networkx.algorithms.planarity import check_planarity

interrupted = False

def signal_handler(sig, frame):
    global interrupted
    print("\n[!] Interrupt received. Saving current progress and exiting...")
    interrupted = True

def _pcp_worker(args):
    base_edge_list, u, v, data = args
    G_test = nx.Graph()
    G_test.add_edges_from(base_edge_list)
    G_test.add_edge(u, v)
    # Boyer-Myrvold is the default algorithm here
    is_planar, _ = check_planarity(G_test, counterexample=False)
    return is_planar, u, v, data

def try_embed(G, u, v, data):
    G.add_edge(u, v, **data)
    is_planar, _ = check_planarity(G, counterexample=False)
    if is_planar:
        return True
    G.remove_edge(u, v)
    return False

def main():
    global interrupted
    signal.signal(signal.SIGINT, signal_handler)

    parser = argparse.ArgumentParser(description='PMFG Builder (NetworkX Optimized)')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--cores', type=int, default=cpu_count())
    parser.add_argument('--saturation', type=float, default=0.95)
    parser.add_argument('--pcp-trigger', type=float, default=0.10)
    parser.add_argument('--edge-attr', type=str, default='profile_similarity')
    args = parser.parse_args()

    print(f"Loading {args.input}...")
    G_input = nx.read_gexf(args.input)
    n = G_input.number_of_nodes()
    
    edges_sorted = sorted(G_input.edges(data=True), 
                          key=lambda e: e[2].get(args.edge_attr, 0.0), reverse=True)

    max_edges = 3 * n - 6
    sat_target = int(args.saturation * max_edges)
    
    G_pmfg = nx.Graph()
    G_pmfg.add_nodes_from(G_input.nodes(data=True))
    
    added = 0
    rejected_count = 0
    edge_idx = 0
    window_results = []
    pcp_active = False

    print(f"Nodes: {n:,} | Max Edges: {max_edges:,} | Target: {sat_target:,}")

    with Pool(processes=args.cores) as pool:
        while edge_idx < len(edges_sorted) and not interrupted:
            if added >= max_edges or added >= sat_target:
                break

            acc_rate = sum(window_results[-200:]) / 200 if len(window_results) >= 200 else 1.0

            if acc_rate < args.pcp_trigger and not pcp_active:
                print(f"\n[Mode] Activating PCP (Rate: {acc_rate:.1%})")
                pcp_active = True

            if pcp_active:
                current_nc = max(args.cores, int((100 * args.cores) * max(acc_rate, 0.01)))
                batch = edges_sorted[edge_idx : edge_idx + current_nc]
                edge_idx += current_nc
                if not batch: break

                base_edges = list(G_pmfg.edges())
                tasks = [(base_edges, u, v, d) for u, v, d in batch]
                results = pool.map(_pcp_worker, tasks)
                
                qualified = [res[1:] for res in results if res[0]]
                
                for u, v, data in qualified:
                    if interrupted or added >= max_edges: break
                    if try_embed(G_pmfg, u, v, data):
                        added += 1
                        window_results.append(True)
                    else:
                        window_results.append(False)
                        rejected_count += 1
                
                print(f" PCP: Checked {edge_idx:,} | Added {added:,}/{sat_target:,} | Rejected {rejected_count:,}")

            else:
                u, v, data = edges_sorted[edge_idx]
                edge_idx += 1
                
                if try_embed(G_pmfg, u, v, data):
                    added += 1
                    window_results.append(True)
                else:
                    window_results.append(False)
                    rejected_count += 1

                if edge_idx % 2000 == 0:
                    print(f" Serial: {edge_idx:,} scanned | {added:,} embedded")

    print(f"\nSaving final graph to {args.output}...")
    nx.write_gexf(G_pmfg, args.output)
    print(f"Success. Final edge count: {G_pmfg.number_of_edges()}")

if __name__ == '__main__':
    main()