"""
genetic_gtsp.py

A readable implementation of a Generalized-Chromosome Genetic Algorithm (GCGA)
for the Generalized Traveling Salesman Problem (GTSP), following the
ideas in Wu et al., Phys. Rev. E (2004).

Chromosome format:
    (head, body)
    - head: list of length m_hat (number of super-vertices / clusters-with-multiple-options)
            each entry is an index selecting which vertex inside that cluster is chosen.
            In our simpler interface we store head for *all* clusters (len = m), but clusters
            with size 1 just have index 0.
    - body: permutation/list of cluster indices (0..m-1) describing visiting order.

Notes:
    - This implementation assumes clusters is a list of lists where each inner list
      contains vertex indices into the global vertex set (0..n-1).
    - Cost matrix W is an n x n matrix-like (supports W[i, j]).
"""

import random
import math
from copy import deepcopy
from typing import List, Tuple, Optional


Chromosome = Tuple[List[int], List[int]]  # (head, body)


class GTSP:
    def __init__(self, cost_matrix, clusters: List[List[int]]):
        """
        cost_matrix: 2D array-like (indexable as W[i][j] or W[i, j])
        clusters: list of clusters, each cluster is a list of vertex indices
        """
        self.W = cost_matrix
        self.clusters = clusters
        self.m = len(clusters)
        # Precompute bounding-box edge length A (used in fitness scaling)
        self.A = self._compute_bounding_box_edge_length()

    def _compute_bounding_box_edge_length(self) -> float:
        # If cost matrix is metric-less, A becomes 1 to avoid zero division.
        # Here we attempt to guess coordinates if W is Euclidean (not required).
        # For safety just return 1.0 (paper uses minimal polytope, but it's optional).
        return 1.0

    def decode(self, chromosome: Chromosome) -> List[int]:
        """
        Return the ordered list of original vertex indices for this chromosome.
        Decoding: pick from each cluster according to head, then order according to body.
        """
        head, body = chromosome
        chosen_vertices = [self.clusters[i][head[i]] for i in range(self.m)]
        ordered = [chosen_vertices[i] for i in body]
        return ordered

    def tour_cost(self, chromosome: Chromosome) -> float:
        """
        Compute the cycle cost for the decoded tour.
        """
        ordered = self.decode(chromosome)
        cost = 0.0
        L = len(ordered)
        for i in range(L):
            a = ordered[i]
            b = ordered[(i + 1) % L]
            cost += float(self.W[a][b])
        return cost

    def best_head_for_body(
        self, body: List[int], current_head: Optional[List[int]] = None
    ) -> List[int]:
        """
        Given a fixed body (order of clusters), find the best head (vertex selection)
        by locally choosing the min-cost vertex for each cluster *w.r.t. neighbors in order*.
        This is a greedy per-cluster optimization: for cluster i, pick vertex v in cluster that
        minimizes cost(prev -> v) + cost(v -> next).
        """
        if current_head is None:
            current_head = [0] * self.m
        # Build neighbor cluster indices for the cycle (in order of body)
        m = self.m
        chosen_head = current_head.copy()
        # For each cluster index (cluster_k), determine predecessor and successor vertices in the cycle
        # We'll choose the vertex within cluster that minimizes the sum of two incident edges.
        # We need the mapping from cluster to position in body
        pos = {cluster_idx: p for p, cluster_idx in enumerate(body)}
        # Precompute chosen vertex for each cluster using initial head
        chosen_vertex = [self.clusters[i][current_head[i]] for i in range(m)]
        # We'll iterate once; more iterations could improve but cost more time.
        for cluster_idx in range(m):
            p = pos[cluster_idx]
            pred_cluster = body[(p - 1) % m]
            succ_cluster = body[(p + 1) % m]
            pred_vertex = chosen_vertex[pred_cluster] if pred_cluster < m else None  # noqa: F841
            succ_vertex = chosen_vertex[succ_cluster] if succ_cluster < m else None  # noqa: F841
            # For each candidate vertex in this cluster compute local incidence cost
            best_v_idx = chosen_head[cluster_idx]
            best_vertex = self.clusters[cluster_idx][best_v_idx]
            best_cost = float("inf")
            for vi_index, vertex in enumerate(self.clusters[cluster_idx]):
                c_pred = (
                    self.W[chosen_vertex[pred_cluster]][vertex]
                    if pred_cluster is not None
                    else 0.0
                )
                c_succ = (
                    self.W[vertex][chosen_vertex[succ_cluster]]
                    if succ_cluster is not None
                    else 0.0
                )
                total = c_pred + c_succ
                if total < best_cost:
                    best_cost = total
                    best_v_idx = vi_index
                    best_vertex = vertex
            chosen_head[cluster_idx] = best_v_idx
            chosen_vertex[cluster_idx] = best_vertex
        return chosen_head


# --------------------------
# Genetic operators
# --------------------------
def init_population(gtsp: GTSP, pop_size: int) -> List[Chromosome]:
    population = []
    for _ in range(pop_size):
        head = [random.randrange(len(c)) for c in gtsp.clusters]
        body = list(range(gtsp.m))
        random.shuffle(body)
        population.append((head, body))
    return population


def tournament_selection(
    population: List[Chromosome], fitnesses: List[float], k: int = 3
) -> Chromosome:
    """Tournament selection: pick k and return best (highest fitness)."""
    selected = random.sample(list(zip(population, fitnesses)), k)
    selected.sort(key=lambda x: x[1], reverse=True)
    return deepcopy(selected[0][0])


def generalized_two_point_crossover(
    parent1: Chromosome, parent2: Chromosome, gtsp: GTSP
) -> Tuple[Chromosome, Chromosome]:
    """
    Generalized two-point crossover:
      - randomly choose two cut points in the generalized chromosome space
      - if both cuts in head region -> exchange head segments
      - if both cuts in body region -> perform order-preserving crossover on body (OX-like)
      - if one in head and one in body -> do both (head segment swap + body OX)
    """
    head1, body1 = deepcopy(parent1[0]), deepcopy(parent1[1])
    head2, body2 = deepcopy(parent2[0]), deepcopy(parent2[1])
    m = gtsp.m
    # Define index space: [0 .. m-1] are head positions (we keep head length == m for simplicity),
    # [m .. m+(m-1)] are body positions (we index body positions relative to m)
    total_len = m + m  # head slots + body slots
    # choose two distinct cut points in [0, total_len)
    i1 = random.randrange(total_len)
    i2 = random.randrange(total_len)
    if i1 > i2:
        i1, i2 = i2, i1

    # Helper to check if index is head or body
    def is_head(idx):
        return idx < m

    # COPY for offspring
    off1_head = head1.copy()
    off2_head = head2.copy()
    off1_body = body1.copy()
    off2_body = body2.copy()

    # Case 1: both in head => swap head segment
    if is_head(i1) and is_head(i2):
        # translate to head positions
        a, b = i1, i2
        for k in range(a, b + 1):
            off1_head[k], off2_head[k] = off2_head[k], off1_head[k]

    # Case 2: both in body => apply order crossover on the body
    elif (not is_head(i1)) and (not is_head(i2)):
        # body indices: subtract m
        a, b = i1 - m, i2 - m

        # Order crossover (OX) style
        def ox(u_body, v_body, a, b):
            size = len(u_body)
            child = [None] * size
            # copy segment u_body[a:b+1]
            for i in range(a, b + 1):
                child[i] = u_body[i]
            # fill remaining from v_body in order
            cur = (b + 1) % size
            vpos = (b + 1) % size
            while None in child:
                if v_body[vpos] not in child:
                    child[cur] = v_body[vpos]
                    cur = (cur + 1) % size
                vpos = (vpos + 1) % size
            return child

        off1_body = ox(body1, body2, a, b)
        off2_body = ox(body2, body1, a, b)

    # Case 3: crossing both head and body -> do both operations
    else:
        # head swap for the head portion intersecting [i1..i2]
        # identify head interval (maybe empty at one side)
        head_a = i1 if is_head(i1) else 0  # noqa: F841
        head_b = (i2 if is_head(i2) else m - 1) if i2 >= 0 else -1  # noqa: F841
        if is_head(i1):
            a = i1
            b = min(i2, m - 1)
            for k in range(a, b + 1):
                off1_head[k], off2_head[k] = off2_head[k], off1_head[k]
        # body part
        if not is_head(i2):
            a = max(0, i1 - m)
            b = i2 - m

            # do OX with a..b on bodies
            def ox(u_body, v_body, a, b):
                size = len(u_body)
                child = [None] * size
                for i in range(a, b + 1):
                    child[i] = u_body[i]
                cur = (b + 1) % size
                vpos = (b + 1) % size
                while None in child:
                    if v_body[vpos] not in child:
                        child[cur] = v_body[vpos]
                        cur = (cur + 1) % size
                    vpos = (vpos + 1) % size
                return child

            off1_body = ox(body1, body2, a, b)
            off2_body = ox(body2, body1, a, b)

    return (off1_head, off1_body), (off2_head, off2_body)  # type: ignore


def insertion_mutation(chrom: Chromosome, gtsp: GTSP, prob: float = 1.0) -> Chromosome:
    """
    Insertion mutation on body: remove one gene and insert at random new position (paper's M operator).
    Head mutation: randomly replace chosen vertex index in a cluster.
    """
    head, body = deepcopy(chrom[0]), deepcopy(chrom[1])
    if random.random() < 0.5:
        # mutate head: pick a cluster and change its selected index
        i = random.randrange(len(head))
        head[i] = random.randrange(len(gtsp.clusters[i]))
    else:
        # insertion mutation on body
        n = len(body)
        if n > 1:
            i = random.randrange(n)
            gene = body.pop(i)
            j = random.randrange(n)  # new insertion position (0..n-1)
            body.insert(j, gene)
    return (head, body)


def generalized_reversion(chrom: Chromosome, gtsp: GTSP) -> Chromosome:
    """
    Reversion operator R: pick two indices in body and reverse the segment between them
    if the reversal decreases the tour cost (local 2-opt style).
    """
    head, body = deepcopy(chrom[0]), deepcopy(chrom[1])
    n = len(body)
    if n < 2:
        return (head, body)
    i, j = sorted(random.sample(range(n), 2))
    if i == j:
        return (head, body)
    # Evaluate cost difference for reversing body[i+1 .. j] relative to neighbors
    # We'll decode to original vertices for the necessary positions
    chosen_vertices = [gtsp.clusters[k][head[k]] for k in range(gtsp.m)]
    # Map body positions to actual vertices
    seq = [chosen_vertices[idx] for idx in body]
    a = seq[i]
    b = seq[(i + 1) % n]
    c = seq[j]
    d = seq[(j + 1) % n]
    # current edges: a-b and c-d ; after reversal: a-c and b-d
    current = gtsp.W[a][b] + gtsp.W[c][d]
    proposed = gtsp.W[a][c] + gtsp.W[b][d]
    if proposed < current:
        # perform reversal on segment (i+1 .. j) inclusive
        new_body = body[: i + 1] + list(reversed(body[i + 1 : j + 1])) + body[j + 1 :]
        return (head, new_body)
    else:
        return (head, body)


# --------------------------
# Fitness / evaluation
# --------------------------
def fitness_from_cost(cost: float, gtsp: GTSP, alpha: float = 1.0) -> float:
    """
    Fitness scaling similar to paper: higher fitness for lower cost.
    f(x) = alpha * sqrt(m) * A / T(x)
    Here A is precomputed (we set to 1 if unknown). Use alpha to scale.
    """
    if cost <= 0:
        return 1e9
    return alpha * math.sqrt(gtsp.m) * gtsp.A / cost


# --------------------------
# Rectification at the end
# --------------------------
def rectify_chromosome(chrom: Chromosome, gtsp: GTSP) -> Chromosome:
    """
    Final cleanup: try to remove rings / duplicate original vertices that may arise due to
    overlapping clusters. Strategy:
      - If two clusters select the same original vertex, try to reselect an alternative vertex
            in at least one of those clusters that yields a strictly better tour cost.
      - Repeat until no duplicates remain or no improvement possible.
    This is greedy and not guaranteed optimal but useful as a final pass.
    """
    head, body = deepcopy(chrom[0]), deepcopy(chrom[1])
    changed = True
    while changed:
        changed = False
        chosen_vertices = [gtsp.clusters[i][head[i]] for i in range(gtsp.m)]
        # Count occurrences by vertex id
        occ = {}
        for c_idx, v in enumerate(chosen_vertices):
            occ.setdefault(v, []).append(c_idx)
        duplicates = {v: idxs for v, idxs in occ.items() if len(idxs) > 1}
        if not duplicates:
            break
        # For each duplicated original vertex, attempt to resolve
        for v, idxs in duplicates.items():
            # try to reassign each cluster in turn (except one) to a different best vertex
            for cluster_idx in idxs:
                best_local_head = head[cluster_idx]
                best_cost_reduction = 0.0
                current_head_value = head[cluster_idx]  # noqa: F841
                current_cost = gtsp.tour_cost((head, body))
                # Try all alternative vertices in that cluster
                for alt_idx, alt_vertex in enumerate(gtsp.clusters[cluster_idx]):
                    if alt_vertex == v:
                        continue
                    trial_head = head.copy()
                    trial_head[cluster_idx] = alt_idx
                    trial_cost = gtsp.tour_cost((trial_head, body))
                    if trial_cost + 1e-12 < current_cost:  # a strict improvement
                        delta = current_cost - trial_cost
                        if delta > best_cost_reduction:
                            best_cost_reduction = delta
                            best_local_head = alt_idx
                if best_cost_reduction > 0:
                    head[cluster_idx] = best_local_head
                    changed = True
                    # break early to recompute occurrences
                    break
            if changed:
                break
        # end for duplicates
    return (head, body)


def run_gcga(
    gtsp: GTSP,
    pop_size: int = 100,
    generations: int = 200,
    crossover_prob: float = 0.89,
    mutation_prob: float = 0.1,
    tournament_k: int = 3,
    elitism: int = 2,
    do_head_reopt: bool = True,
) -> Tuple[Chromosome, float]:
    """
    Run GCGA and return best found chromosome and its cost.
    """
    population = init_population(gtsp, pop_size)
    # optional initial head reopt
    if do_head_reopt:
        population = [
            (gtsp.best_head_for_body(chrom[1], chrom[0]), chrom[1])
            for chrom in population
        ]

    # evaluate
    fitnesses = [fitness_from_cost(gtsp.tour_cost(ind), gtsp) for ind in population]

    best = None
    best_cost = float("inf")

    for gen in range(generations):
        # if gen % 100 == 0:
        # 	print("Generation", gen, "best cost so far:", best_cost)

        # Sort population by fitness descending
        pop_with_fit = list(zip(population, fitnesses))
        pop_with_fit.sort(key=lambda x: x[1], reverse=True)
        # elitism
        new_population = [deepcopy(x[0]) for x in pop_with_fit[:elitism]]

        # update best
        cand_cost = gtsp.tour_cost(pop_with_fit[0][0])
        if cand_cost < best_cost:
            best_cost = cand_cost
            best = deepcopy(pop_with_fit[0][0])

        # build next generation
        while len(new_population) < pop_size:
            # selection
            p1 = tournament_selection(population, fitnesses, k=tournament_k)
            p2 = tournament_selection(population, fitnesses, k=tournament_k)
            # crossover
            if random.random() < crossover_prob:
                c1, c2 = generalized_two_point_crossover(p1, p2, gtsp)
            else:
                c1, c2 = deepcopy(p1), deepcopy(p2)
            # mutation
            if random.random() < mutation_prob:
                c1 = insertion_mutation(c1, gtsp)
            if random.random() < mutation_prob:
                c2 = insertion_mutation(c2, gtsp)
            # reversion (2-opt) tries
            c1 = generalized_reversion(c1, gtsp)
            c2 = generalized_reversion(c2, gtsp)
            # optional local head reopt for offspring
            if do_head_reopt:
                c1 = (gtsp.best_head_for_body(c1[1], c1[0]), c1[1])
                c2 = (gtsp.best_head_for_body(c2[1], c2[0]), c2[1])
            new_population.append(c1)
            if len(new_population) < pop_size:
                new_population.append(c2)

        population = new_population
        fitnesses = [fitness_from_cost(gtsp.tour_cost(ind), gtsp) for ind in population]

    # final rectification of best
    best = rectify_chromosome(best, gtsp)  # type: ignore
    best_cost = gtsp.tour_cost(best)
    return best, best_cost
