import itertools
import time
from gurobipy import Model, GRB, quicksum


class Points:
    def __init__(self, x_coordinate, y_coordinate):
        self.x_coordinate = x_coordinate
        self.y_coordinate = y_coordinate

    def __str__(self):
        return f"({self.x_coordinate}, {self.y_coordinate})"


def calculate_distance(point1, point2):
    x_distance = 1.1 * abs(point1.x_coordinate - point2.x_coordinate)
    y_distance = abs(point1.y_coordinate - point2.y_coordinate)
    return max(x_distance, y_distance)


def get_distance_dict(file_path):
    global points_dict
    points_dict = {}
    points_dict[0] = Points(0, 0)
    with open(file_path, 'r') as file:
        num_of_points = int(file.readline().strip())
        for i in range(1, num_of_points + 1):
            _, x, y = file.readline().split()
            points_dict[i] = Points(float(x), float(y))

    # Generate point combinations and calculate distances
    distance_dict = {}
    for combination in itertools.permutations(points_dict.keys(), 2):
        distance_dict[combination] = calculate_distance(
            points_dict[combination[0]], points_dict[combination[1]])

    return distance_dict


def twoOpt(tour, distance_dict):
    start_time = time.time()
    tour = tour[:-1]
    n = len(tour)
    improvement = True
    old_distance = calculate_total_distance(
        distance_dict=distance_dict, route=tour, nn=True)
    while improvement:
        improvement = False
        for i in range(1, n-1):
            if time.time() - start_time > 300:  # 300 seconds = 5 minutes
                print("Time exceeded 5 minutes")
                return tour

            for j in range(i+1, n):
                new_tour = tour[0:i] + tour[i:j + 1][::-1] + tour[j + 1:n]
                new_distance = calculate_total_distance(
                    distance_dict=distance_dict, route=new_tour, nn=True)
                if new_distance < old_distance:
                    print("Improvement found: New length =", new_distance)
                    tour = new_tour
                    improvement = True
                    break

            if improvement:
                old_distance = new_distance
                print("Improvement made in inner loop, returning to the outer loop.")
                break
    tour.append(0)
    return tour


def plot_tour(points, route, nn=False):
    plt.figure(figsize=(10, 6))

    # Plot the points
    for point in points.values():
        plt.plot(point.x_coordinate, point.y_coordinate, 'bo')

    if nn:
        # Draw the paths
        for k in range(len(route)-1):
            i = route[k]
            j = route[k+1]
            plt.plot([points[i].x_coordinate, points[j].x_coordinate], [
                points[i].y_coordinate, points[j].y_coordinate], 'b-')
    else:
        for i, j in route:
            plt.plot([points[i].x_coordinate, points[j].x_coordinate], [
                points[i].y_coordinate, points[j].y_coordinate], 'b-')

    plt.xlabel('X coordinate')
    plt.ylabel('Y coordinate')
    plt.title('Optimal Tour')
    plt.grid(True)
    plt.show()


# plot_tour(points_dict, route)

def nearest_neighbour_v2(distance_dict, points):
    print("NN started")

    point_to_connections = {p: {} for p in points}
    for (p1, p2), dist in distance_dict.items():
        point_to_connections[p1][p2] = dist
        point_to_connections[p2][p1] = dist

    def find_nearest_point(point, unvisited_points):
        closest_point, min_distance = None, float('inf')
        connections = point_to_connections[point]
        for p, dist in connections.items():
            if p in unvisited_points and dist < min_distance:
                closest_point, min_distance = p, dist
        return closest_point

    tour = [0]
    unvisited_points = set(points)
    unvisited_points.remove(0)
    current_point = 0
    while unvisited_points:
        print(f"Cities left to visit: {len(unvisited_points)}")
        nearest_point = find_nearest_point(current_point, unvisited_points)
        tour.append(nearest_point)
        unvisited_points.remove(nearest_point)
        current_point = nearest_point

    tour.append(0)
    return tour


def calculate_total_distance(distance_dict, route, nn=False):
    total_distance = 0
    if nn:
        for k in range(len(route)-1):
            i = route[k]
            j = route[k+1]
            total_distance += distance_dict[(int(i), int(j))]
    else:
        for travel in route:
            total_distance += distance_dict[travel]

    return total_distance


def load_initial_solution(model, initial_tour, vars, u):
    # Reset the start attribute for all variables to 0
    for var in vars.values():
        var.start = 0

    # Set the start attribute to 1 for edges in the initial tour
    tour_edges = zip(initial_tour[:-1], initial_tour[1:])
    for i, j in tour_edges:
        if (i, j) in vars:
            vars[i, j].start = 1

    # Initialize subtour elimination variables based on the order in the tour
    # Exclude the return to the start
    for index, city in enumerate(initial_tour[:-1]):
        u[city].start = index + 1  # Position in the tour, starting from 1


def optimize_tsp_with_initial_solution(distance_dict, points, initial_tour, time):
    model = Model("TSP")

    # Decision variables: x[i, j] is 1 if the path is part of the route, else 0
    vars = {}
    for (i, j) in distance_dict.keys():
        vars[i, j] = model.addVar(
            obj=distance_dict[i, j], vtype=GRB.BINARY, name=f"x_{i}_{j}")

    # Subtour elimination variables: u[i] is the position of point i in the tour
    u = model.addVars(points, vtype=GRB.CONTINUOUS, name='u')

    # Constraints: Each city must be entered and left exactly once
    for i in points:
        model.addConstr(quicksum(vars[i, j] for j in points if (
            i, j) in vars) == 1, name=f"enter_{i}")
        model.addConstr(quicksum(vars[j, i] for j in points if (
            j, i) in vars) == 1, name=f"leave_{i}")

    # Subtour elimination constraints (skip for the start city 0)
    for i in points:
        for j in points:
            if i != j and (i != 0 and j != 0) and (i, j) in vars:
                model.addConstr(u[i] - u[j] + len(points) * vars[i, j]
                                <= len(points) - 1, name=f"subtour_{i}_{j}")

    # Constraint for point 0 to start and end the tour
    model.addConstr(quicksum(vars[0, j] for j in points if (
        0, j) in vars) == 1, name="leave_0")
    model.addConstr(quicksum(vars[i, 0] for i in points if (
        i, 0) in vars) == 1, name="enter_0")

    # Load initial solution
    print("Initial solution loaded...")
    load_initial_solution(model, initial_tour, vars, u)

    # Set the model to focus on finding a feasible solution quickly
    model.Params.timeLimit = time * 60
    model.setParam('MIPFocus', 1)

    # Optimize the model
    model.optimize()

    if model.SolCount > 0:
        # A feasible solution is available
        mip_gap = model.MIPGap
        print(f"The solution is within {mip_gap:.2%} of the optimal value.")
        solution = model.getAttr('X', vars)
        route = [(i, j) for i, j in solution if solution[i, j] > 0.5]
        objective_value = model.ObjVal
        return route
    else:
        # Handle cases where no feasible solution is found
        if model.status == GRB.TIME_LIMIT:
            print("No feasible solution found within the time limit.")
        else:
            print("Optimization was unsuccessful. Status code:", model.status)
        return None
