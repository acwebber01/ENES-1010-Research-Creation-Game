import pygame
import math
import random

pygame.init()

RESOLUTION_1080 = (800, 1000)
RESOLUTION_720 = (1280, 720)
current_resolution = RESOLUTION_1080
WIDTH, HEIGHT = current_resolution

PLAYING_FIELD_HEIGHT = 3000
PLAYING_FIELD_WIDTH = 3000
NUM_STARS = 500
G = 6.674e-3
MAX_SPEED = 5

# background cosmetic stars =) 
stars = [
    pygame.Vector2(random.uniform(-100, PLAYING_FIELD_WIDTH + 100),
                   random.uniform(-100, PLAYING_FIELD_HEIGHT + 1000))
    for _ in range(NUM_STARS)
]

VEC_ORIGIN = pygame.Vector2(WIDTH - 100, HEIGHT - 100)
VEC_SCALE = 5

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("simple space exploration with a physics changer")
clock = pygame.time.Clock()

class MotionModel:
    def apply(self, obj, all_bodies): pass

class NewtonianMotion(MotionModel):
    def apply(self, obj, all_bodies):
        if isinstance(obj, Ship) and obj.landed:
            return
        obj.net_acceleration = pygame.Vector2(0, 0)
        for other in all_bodies:
            if other is obj: continue
            r_vec = other.position - obj.position
            r2 = r_vec.length_squared()
            if r2 > 1:
                force_mag = G * other.mass / r2
                acc = r_vec.normalize() * force_mag
                obj.net_acceleration += acc
                obj.velocity += acc
        obj.velocity += obj.acceleration
        obj.net_acceleration += obj.acceleration
        obj.position += obj.velocity
        if obj.velocity.length() > MAX_SPEED:
            obj.velocity.scale_to_length(MAX_SPEED)

class BuridanMotion(MotionModel):
    def apply(self, obj, all_bodies):
        if isinstance(obj, Ship) and obj.landed:
            return
        obj.net_acceleration = pygame.Vector2(0, 0)
        obj.velocity *= 0.9999
        gravity_force = pygame.Vector2(0, 1) * 0.1
        obj.net_acceleration += gravity_force
        obj.velocity += gravity_force
        obj.velocity += obj.acceleration
        obj.net_acceleration += obj.acceleration
        obj.position += obj.velocity
        if obj.velocity.length() > MAX_SPEED:
            obj.velocity.scale_to_length(MAX_SPEED)

class AristotelianMotion(MotionModel):
    def apply(self, obj, all_bodies):
        if isinstance(obj, Ship) and obj.landed:
            return
        obj.net_acceleration = pygame.Vector2(0, 0)
        gravity_acc = pygame.Vector2(0, 0) * 0.5 * obj.mass / 100 if obj.natural else pygame.Vector2(0, 0)
        obj.net_acceleration += gravity_acc
        if obj.thrusting:
            thrust_acc = obj.acceleration * 25
            obj.velocity = thrust_acc + gravity_acc
        else:
            obj.velocity += obj.net_acceleration
            if gravity_acc.length_squared() == 0:
                obj.velocity = pygame.Vector2(0, 0)
        obj.position += obj.velocity
        if obj.velocity.length() > MAX_SPEED:
            obj.velocity.scale_to_length(MAX_SPEED)

class PhysicsBody:
    def __init__(self, x, y, radius, motion_model):
        self.position = pygame.Vector2(x, y)
        self.velocity = pygame.Vector2(0, 0)
        self.acceleration = pygame.Vector2(0, 0)
        self.net_acceleration = pygame.Vector2(0, 0)
        self.radius = radius
        self.angle = 0
        self.thrusting = False
        self.motion_model = motion_model
        self.mass = self.radius ** 2
        self.natural = False
        self.impetus = pygame.Vector2(0, 0)

    def update(self):
        if isinstance(self.motion_model, AristotelianMotion):
            self.impetus = self.velocity
        else:
            if self.impetus.length_squared() > 0:
                self.velocity = self.impetus
                self.impetus = pygame.Vector2(0, 0)
        self.motion_model.apply(self, all_bodies)

    def draw(self, surface, camera_offset):
        screen_pos = self.position - camera_offset
        pygame.draw.circle(surface, (0, 0, 0), (int(screen_pos.x), int(screen_pos.y)), self.radius)

    def check_collision(self, other):
        if isinstance(self, Planet) and self == goal_planet:
            return False
        if isinstance(other, Planet) and other == goal_planet:
            return False
        return self.position.distance_to(other.position) < self.radius + other.radius

class Ship(PhysicsBody):
    def __init__(self, motion_model):
        super().__init__(WIDTH // 2, HEIGHT // 2, 10, motion_model)
        self.thrust_force = 50
        self.thrust_force_min = 1
        self.thrust_force_max = 100
        self.thrust_force_step = 1
        self.mass = 100
        self.natural = True
        self.landed = False
        self.fuel = 100
        self.oxygen = 100
        self.hull = 100
        self.resource_transfer_rate = 1
        self.cash = 1000
        self.shoot_cooldown = 0
        self.shoot_delay = 10
        self.projectiles = []
        self.max_fuel = 100
        self.max_hull = 100
        self.oxygen_depletion_rate = 0.05
        self.min_depletion_rate = 0.01

    def rotate(self, direction):
        if self.landed: return
        if self.fuel > 0:
            self.angle += direction * 3
            self.fuel = max(0, self.fuel - 0.05)
        else:
            self.angle += direction * 1

    def apply_thrust(self):
        if not self.landed and self.fuel > 0:
            rad = math.radians(self.angle)
            thrust_vector = pygame.Vector2(math.sin(rad), -math.cos(rad)) * self.thrust_force / 100
            self.acceleration = thrust_vector
            self.thrusting = True
            self.fuel = max(0, self.fuel - self.thrust_force * 0.001)

    def stop_thrust(self):
        self.acceleration = pygame.Vector2(0, 0)
        self.thrusting = False

    def land(self, planet):
        self.landed = True
        self.velocity = pygame.Vector2(0, 0)
        self.acceleration = pygame.Vector2(0, 0)
        direction_to_planet = (self.position - planet.position).normalize()
        self.position = planet.position + direction_to_planet * (planet.radius + self.radius)
        self.current_planet = planet
        planet.harvested = True

    def take_off(self):
        self.landed = False
        rad = math.radians(self.angle)
        launch_vector = pygame.Vector2(math.sin(rad), -math.cos(rad)) * 5
        self.velocity += launch_vector

    def update(self):
        super().update()
        self.shoot_cooldown = max(0, self.shoot_cooldown - 1)
        self.projectiles = [p for p in self.projectiles if p.lifetime > 0]
        for projectile in self.projectiles:
            projectile.update()

        if not self.landed and self.oxygen > 0:
            self.oxygen = round(max(0, self.oxygen - self.oxygen_depletion_rate), 2)

        if self.landed and self.current_planet:
            # Resource transfer logic
            fuel_needed = self.max_fuel - self.fuel
            oxygen_needed = 100 - self.oxygen
            hull_needed = self.max_hull - self.hull
            ore_to_take = min(hull_needed, self.resource_transfer_rate, self.current_planet.ore)
            self.hull = round(min(self.max_hull, self.hull + ore_to_take), 2)
            self.current_planet.ore = round(self.current_planet.ore - ore_to_take, 2)

            
            if self.hull >= self.max_hull and self.current_planet.ore > 0:
                ore_to_cash = min(self.current_planet.ore, self.resource_transfer_rate)
                self.cash += ore_to_cash
                self.current_planet.ore = round(self.current_planet.ore - ore_to_cash, 2)

            fuel_to_take = min(fuel_needed, self.resource_transfer_rate, self.current_planet.fuel)
            oxygen_to_take = min(oxygen_needed, self.resource_transfer_rate, self.current_planet.oxygen)
            self.fuel = round(self.fuel + fuel_to_take, 2)
            self.oxygen = round(self.oxygen + oxygen_to_take, 2)
            self.fuel = round(min(self.max_fuel, self.fuel + fuel_to_take), 2)
            self.oxygen = round(min(100, self.oxygen + oxygen_to_take), 2)
            if (self.current_planet.fuel <= 0 and 
                self.current_planet.oxygen <= 0 and 
                self.current_planet.ore <= 0):
                self.current_planet = None

    def take_damage(self, collision_force):
        self.hull = max(0, self.hull - collision_force * 10)

    def shoot(self):
        if self.shoot_cooldown == 0:
            rad = math.radians(self.angle)
            nose_offset = pygame.Vector2(math.sin(rad), -math.cos(rad)) * self.radius
            proj = Projectile(self.position.x + nose_offset.x, 
                            self.position.y + nose_offset.y,
                            self.angle, self.motion_model)
            self.projectiles.append(proj)
            self.shoot_cooldown = self.shoot_delay

    def buy_upgrade(self, upgrade_type):
        global MAX_SPEED
        if not self.current_planet or not self.current_planet.is_shop:
            return False
        if upgrade_type not in self.current_planet.upgrades:
            return False
        cost, amount = self.current_planet.upgrades[upgrade_type]
        if self.cash < cost:
            return False
        self.cash -= cost
        if upgrade_type == 'max_fuel':
            self.max_fuel += amount
            self.fuel = min(self.fuel, self.max_fuel)
        elif upgrade_type == 'max_hull':
            self.max_hull += amount
            self.hull = min(self.hull, self.max_hull)
        elif upgrade_type == 'thrust':
            self.thrust_force_max += amount
            MAX_SPEED += amount / 10
        elif upgrade_type == 'shoot_delay':
            self.shoot_delay = max(5, self.shoot_delay + amount)
        elif upgrade_type == 'oxygen_efficiency':
            self.oxygen_depletion_rate = max(self.min_depletion_rate, self.oxygen_depletion_rate - amount)
        return True

    def draw(self, surface, camera_offset):
        for projectile in self.projectiles:
            projectile.draw(surface, camera_offset)
        points = [pygame.Vector2(0, -10), pygame.Vector2(5, 10), pygame.Vector2(-5, 10)]
        rotated_points = [p.rotate(self.angle) + self.position - camera_offset for p in points]
        pygame.draw.polygon(surface, (255, 255, 255), rotated_points)
        if self.thrusting:
            flame_points = [
                pygame.Vector2(0, 15),
                pygame.Vector2(-3, 10),
                pygame.Vector2(3, 10)
            ]
            rotated_flame = [p.rotate(self.angle) + self.position - camera_offset for p in flame_points]
            pygame.draw.polygon(surface, (255, 165, 0), rotated_flame)
        fuel_bar_width = 40
        fuel_bar_height = 5
        fuel_bar_x = self.position.x - camera_offset.x - fuel_bar_width // 2
        fuel_bar_y = self.position.y - camera_offset.y - self.radius - 15
        fuel_percentage = self.fuel / self.max_fuel
        pygame.draw.rect(surface, (255, 0, 0), (fuel_bar_x, fuel_bar_y, fuel_bar_width, fuel_bar_height))
        pygame.draw.rect(surface, (0, 255, 0), (fuel_bar_x, fuel_bar_y, fuel_bar_width * fuel_percentage, fuel_bar_height))
        oxygen_bar_width = 40
        oxygen_bar_height = 5
        oxygen_bar_x = self.position.x - camera_offset.x - oxygen_bar_width // 2
        oxygen_bar_y = self.position.y - camera_offset.y - self.radius - 25
        oxygen_percentage = self.oxygen / 100
        pygame.draw.rect(surface, (255, 0, 0), (oxygen_bar_x, oxygen_bar_y, oxygen_bar_width, oxygen_bar_height))
        pygame.draw.rect(surface, (0, 0, 255), (oxygen_bar_x, oxygen_bar_y, oxygen_bar_width * oxygen_percentage, oxygen_bar_height))
        hull_bar_width = 40
        hull_bar_height = 5
        hull_bar_x = self.position.x - camera_offset.x - hull_bar_width // 2
        hull_bar_y = self.position.y - camera_offset.y - self.radius - 35
        hull_percentage = self.hull / self.max_hull
        pygame.draw.rect(surface, (255, 0, 0), (hull_bar_x, hull_bar_y, hull_bar_width, hull_bar_height))
        pygame.draw.rect(surface, (255, 255, 0), (hull_bar_x, hull_bar_y, hull_bar_width * hull_percentage, hull_bar_height))
        font = pygame.font.SysFont(None, 24)

        surface.blit(font.render(f"Fuel: {self.fuel:.2f}%", True, (255, 255, 255)), (10, 40))
        surface.blit(font.render(f"Oxygen: {self.oxygen:.2f}%", True, (255, 255, 255)), (10, 60))
        surface.blit(font.render(f"Hull: {self.hull:.2f}%", True, (255, 255, 255)), (10, 80))
        surface.blit(font.render(f"Cash: {self.cash:.2f}", True, (255, 215, 0)), (10, 100)) 

class PhysicsObject(PhysicsBody): pass

class Planet(PhysicsBody):
    def __init__(self, x, y, radius, motion_model, color, goal_planet=None):
        super().__init__(x, y, radius, motion_model)
        self.mass = (self.radius ** 2) * 100
        self.color = color
        self.fuel = random.randint(10, 50)
        self.oxygen = random.randint(10, 50)
        self.ore = random.randint(10, 50)
        self.harvested = False
        self.is_shop = False
        self.upgrades = {}
        if goal_planet:
            self.mass *= 10

    def setup_as_shop(self):
        # print("Setting up planet as shop")
        self.is_shop = True
        self.color = (218, 165, 32)
        self.fuel = 100
        self.oxygen = 100
        self.ore = 100
        self.upgrades = {
            'max_fuel': (50, 25),
            'max_hull': (75, 25),
            'thrust': (100, 25),
            'shoot_delay': (150, -2),
            'oxygen_efficiency': (200, 0.01),
        }

    def update(self):
        if self.fuel <= 0 and self.oxygen <= 0 and self.ore <= 0:
            self.harvested = True

    def draw(self, surface, camera_offset):
        screen_pos = self.position - camera_offset
        if self == goal_planet:
            for i in range(10):
                alpha = 255 - (i * 25)
                color = (0, 255, 255, alpha)
                pygame.draw.circle(surface, color, (int(screen_pos.x), int(screen_pos.y)), self.radius - i * 5, 1)
        else:
            pygame.draw.circle(surface, self.color, (int(screen_pos.x), int(screen_pos.y)), self.radius)

        if self != goal_planet:
            font = pygame.font.SysFont(None, 18)
            resource_text = f"Fuel: {self.fuel:.2f}, O2: {self.oxygen:.2f}, Ore: {self.ore:.2f}"
            text_surface = font.render(resource_text, True, (255, 255, 255))
            surface.blit(text_surface, (screen_pos.x - self.radius, screen_pos.y - self.radius - 10))

        if self.harvested and self != goal_planet:
            harvested_text = font.render("Harvested", True, (255, 0, 0))
            surface.blit(harvested_text, (screen_pos.x - self.radius, screen_pos.y - self.radius - 25))

class Asteroid(PhysicsObject):
    def __init__(self, x, y, radius, motion_model, color):
        super().__init__(x, y, radius, motion_model)
        self.color = color
        self.mass = (self.radius ** 2) * 1000
        self.velocity = pygame.Vector2(random.uniform(-1, 1), random.uniform(1, 25))
        self.inertia_resistance = 0.95

    def update(self):
        original_velocity = self.velocity.copy()
        super().update()
        self.velocity = self.velocity * (1 - self.inertia_resistance) + original_velocity * self.inertia_resistance

    def draw(self, surface, camera_offset):
        screen_pos = self.position - camera_offset
        pygame.draw.circle(surface, self.color, (int(screen_pos.x), int(screen_pos.y)), self.radius)
        pygame.draw.circle(surface, (0, 0, 0), (int(screen_pos.x), int(screen_pos.y)), self.radius, 1)

class EnemyShip(PhysicsBody):
    def __init__(self, x, y, motion_model):
        super().__init__(x, y, 10, motion_model)
        self.color = (255, 0, 0)
        self.mass = 200
        self.speed = 2
        self.aristotle_speed = 0.2
        self.thrusting = True
        self.natural = True
        self.fuel = 100
        self.hull = 100
        self.detection_radius = 500
        self.pursuing = False

    def update(self):
        distance_to_player = (ship.position - self.position).length()
        self.pursuing = distance_to_player <= self.detection_radius
        
        if self.pursuing and self.fuel > 0:
            direction = (ship.position - self.position)
            if direction.length_squared() > 0:
                direction = direction.normalize()
                self.angle = math.degrees(math.atan2(direction.x, -direction.y))
                
                if isinstance(self.motion_model, AristotelianMotion):
                    self.acceleration = direction * self.aristotle_speed
                    self.thrusting = True
                else:
                    self.velocity = direction * self.speed
                self.fuel = max(0, self.fuel - 0.025)
        else:
            if not isinstance(self.motion_model, AristotelianMotion):
                self.velocity *= 0.98

        super().update()

    def draw(self, surface, camera_offset):
        points = [pygame.Vector2(0, -10), pygame.Vector2(5, 10), pygame.Vector2(-5, 10)]
        rotated_points = [p.rotate(self.angle) + self.position - camera_offset for p in points]
        pygame.draw.polygon(surface, self.color, rotated_points)

        if self.velocity.length_squared() > 0:
            flame_points = [
                pygame.Vector2(0, 15),
                pygame.Vector2(-3, 10),
                pygame.Vector2(3, 10)
            ]
            rotated_flame = [p.rotate(self.angle) + self.position - camera_offset for p in flame_points]
            pygame.draw.polygon(surface, (255, 165, 0), rotated_flame)

        bar_width = 40
        bar_height = 5

        fuel_bar_x = self.position.x - camera_offset.x - bar_width // 2
        fuel_bar_y = self.position.y - camera_offset.y - self.radius - 15
        pygame.draw.rect(surface, (255, 0, 0), (fuel_bar_x, fuel_bar_y, bar_width, bar_height))
        pygame.draw.rect(surface, (0, 255, 0), (fuel_bar_x, fuel_bar_y, bar_width * (self.fuel/100), bar_height))

        hull_bar_y = self.position.y - camera_offset.y - self.radius - 25
        pygame.draw.rect(surface, (255, 0, 0), (fuel_bar_x, hull_bar_y, bar_width, bar_height))
        pygame.draw.rect(surface, (255, 255, 0), (fuel_bar_x, hull_bar_y, bar_width * (self.hull/100), bar_height))

    def take_damage(self, collision_force):
        self.hull = max(0, self.hull - collision_force * 10)

class Projectile(PhysicsObject):
    def __init__(self, x, y, angle, motion_model):
        super().__init__(x, y, 3, motion_model)
        self.speed = 8
        rad = math.radians(angle)
        self.velocity = pygame.Vector2(math.sin(rad), -math.cos(rad)) * self.speed
        self.lifetime = 600 #in frames
        self.damage = 25

    def update(self):
        super().update()
        self.lifetime -= 1

    def draw(self, surface, camera_offset):
        screen_pos = self.position - camera_offset
        pygame.draw.circle(surface, (255, 255, 0), (int(screen_pos.x), int(screen_pos.y)), self.radius)

motion_newton = NewtonianMotion()
motion_buridan = BuridanMotion()
motion_aristotle = AristotelianMotion()
current_motion_model = motion_newton

PLAYING_FIELD_WIDTH = 3000
PLAYING_FIELD_HEIGHT = 15000
NUM_PLANETS = 10
MIN_PLANET_DISTANCE = 1500

planets = []
while len(planets) < NUM_PLANETS:
    x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
    y = random.randint(100, PLAYING_FIELD_HEIGHT - 100)
    radius = random.randint(50, 150)
    color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
    if all(math.hypot(x - p.position.x, y - p.position.y) > MIN_PLANET_DISTANCE + p.radius + radius for p in planets):
        planets.append(Planet(x, y, radius, current_motion_model, color))

starting_planet = Planet(PLAYING_FIELD_WIDTH // 2, PLAYING_FIELD_HEIGHT - 200, 150, current_motion_model, (139, 69, 19))
starting_planet.fuel = 0
starting_planet.oxygen = 0
starting_planet.ore = 0

goal_planet_x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
goal_planet = Planet(goal_planet_x, 200, 150, current_motion_model, (0, 255, 0), True)

shop_planet = Planet(random.randint(100, PLAYING_FIELD_WIDTH - 100),
                    random.randint(400, PLAYING_FIELD_HEIGHT - 400),
                    100, current_motion_model, (218, 165, 32))
shop_planet.setup_as_shop()

planets.append(starting_planet)
planets.append(goal_planet)
planets.append(shop_planet)

# print(f"Total planets: {len(planets)}")
# print(f"Shop planet exists: {any(p.is_shop for p in planets)}")

ship = Ship(current_motion_model)
ship.position = starting_planet.position + pygame.Vector2(0, -starting_planet.radius - ship.radius)
ship.landed = True
ship.current_planet = starting_planet

NUM_ASTEROIDS = 35
asteroids = []

NUM_ENEMY_SHIPS = 12
levels_completed = 0
enemy_ships = []

COLOR_CHANGE_SPEED = 6 # Higher number = slower color change

all_bodies = []

def draw_arrow(surface, start, end, color, width=2):
    if start == end:
        return
    direction = end - start
    if direction.length_squared() == 0:
        return
    direction = direction.normalize()
    arrow_size = 20
    arrow_width = 10
    left = end - direction * arrow_size + direction.rotate(90) * (arrow_width / 2)
    right = end - direction * arrow_size - direction.rotate(90) * (arrow_width / 2)
    pygame.draw.line(surface, color, start, end, width)
    pygame.draw.polygon(surface, color, [end, left, right])

def draw_compass(surface, ship_position, goal_position):
    compass_center = pygame.Vector2(WIDTH // 2, HEIGHT - 50)
    compass_radius = 40
    pygame.draw.circle(surface, (200, 200, 200), compass_center, compass_radius, 2)

    shop_planet = next((p for p in planets if p.is_shop), None)

    direction = (goal_position - ship_position).normalize()
    compass_arrow_end = compass_center + direction * (compass_radius - 10)
    pygame.draw.line(surface, (255, 0, 0), compass_center, compass_arrow_end, 3)

    if shop_planet:
        shop_direction = (shop_planet.position - ship_position).normalize()
        shop_arrow_end = compass_center + shop_direction * (compass_radius - 10)
        pygame.draw.line(surface, (255, 255, 0), compass_center, shop_arrow_end, 2)

def interpolate_color(color1, color2, blend_ratio):
    return (
        int(color1[0] * (1 - blend_ratio) + color2[0] * blend_ratio),
        int(color1[1] * (1 - blend_ratio) + color2[1] * blend_ratio),
        int(color1[2] * (1 - blend_ratio) + color2[2] * blend_ratio),
    )

def draw_gradient_background(surface, color_top_start, color_top_end, color_bottom_start, color_bottom_end, time_offset):
    blend_ratio = (math.sin(time_offset / COLOR_CHANGE_SPEED) + 1) / 2
    color_top = interpolate_color(color_top_start, color_top_end, blend_ratio)
    color_bottom = interpolate_color(color_bottom_start, color_bottom_end, blend_ratio)
    for y in range(HEIGHT):
        vertical_blend_ratio = y / HEIGHT
        blended_color = interpolate_color(color_top, color_bottom, vertical_blend_ratio)
        pygame.draw.line(surface, blended_color, (0, y), (WIDTH, y))

running = True
game_over = False
oxygen_depletion_time = None

def generate_new_level(levelOne=False):
    global planets, all_bodies, starting_planet, goal_planet, ship, asteroids, enemy_ships, levels_completed
    if not levelOne:
        levels_completed += 1

    planets = []
    asteroids = []
    enemy_ships = []

    while len(planets) < NUM_PLANETS:
        x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
        y = random.randint(100, PLAYING_FIELD_HEIGHT - 100)
        radius = random.randint(50, 150)
        color = (random.randint(50, 255), random.randint(50, 255), random.randint(50, 255))
        if all(math.hypot(x - p.position.x, y - p.position.y) > MIN_PLANET_DISTANCE + p.radius + radius for p in planets):
            planets.append(Planet(x, y, radius, current_motion_model, color))

    if not levelOne and random.choice([True, False]):
        starting_planet = Planet(PLAYING_FIELD_WIDTH // 2, 200, 150, current_motion_model, (150, 75, 0))
        goal_planet_x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
        goal_planet = Planet(goal_planet_x, PLAYING_FIELD_HEIGHT - 200, 150, current_motion_model, (0, 255, 0), True)
    else:
        starting_planet = Planet(PLAYING_FIELD_WIDTH // 2, PLAYING_FIELD_HEIGHT - 200, 150, current_motion_model, (150, 75, 0))
        goal_planet_x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
        goal_planet = Planet(goal_planet_x, 200, 150, current_motion_model, (0, 255, 0), True)

    planets.append(starting_planet)
    planets.append(goal_planet)

    for _ in range(NUM_ASTEROIDS):
        x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
        y = random.randint(100, PLAYING_FIELD_HEIGHT - 100)
        radius = random.randint(10, 30)
        asteroids.append(Asteroid(x, y, radius, current_motion_model, (128, 128, 128)))

    base_enemies = NUM_ENEMY_SHIPS
    bonus_enemies = levels_completed * 2
    total_enemies = min(base_enemies + bonus_enemies, 50)
    for _ in range(total_enemies):
        x = random.randint(100, PLAYING_FIELD_WIDTH - 100)
        y = random.randint(100, PLAYING_FIELD_HEIGHT - 100)
        enemy_ships.append(EnemyShip(x, y, current_motion_model))

    saved_cash = ship.cash
    if starting_planet.position.y == 200:
        ship.position = starting_planet.position + pygame.Vector2(0, starting_planet.radius + ship.radius)
        ship.angle = 180
    else:
        ship.position = starting_planet.position + pygame.Vector2(0, -starting_planet.radius - ship.radius)
        ship.angle = 0

    ship.velocity = pygame.Vector2(0, 0)
    ship.acceleration = pygame.Vector2(0, 0)
    ship.landed = True
    ship.current_planet = starting_planet
    ship.fuel = 100
    ship.oxygen = 100
    ship.hull = 100
    ship.cash = saved_cash

    all_bodies = planets + asteroids + enemy_ships + [ship]

    valid_planets = [p for p in planets if p != starting_planet and p != goal_planet]
    if valid_planets:
        random.choice(valid_planets).setup_as_shop()

    
time_offset = 0
generate_new_level(True)

def toggle_resolution():
    global WIDTH, HEIGHT, current_resolution, screen, VEC_ORIGIN
    if current_resolution == RESOLUTION_1080:
        current_resolution = RESOLUTION_720
    else:
        current_resolution = RESOLUTION_1080
    WIDTH, HEIGHT = current_resolution
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    VEC_ORIGIN = pygame.Vector2(WIDTH - 150, HEIGHT - 100)

while running:
    if game_over:
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont(None, 72)
        game_over_text = font.render("Game Over", True, (255, 0, 0))
        screen.blit(game_over_text, (WIDTH // 2 - game_over_text.get_width() // 2, HEIGHT // 2))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        continue

    time_offset += 0.01
    draw_gradient_background(
        screen,
        (75, 0, 130),
        (255, 0, 0),
        (0, 0, 50),
        (0, 255, 255),
        time_offset
    )

    camera_offset = ship.position - pygame.Vector2(WIDTH // 2, HEIGHT // 2)
    camera_offset.x = max(0, min(camera_offset.x, PLAYING_FIELD_WIDTH - WIDTH))
    camera_offset.y = max(0, min(camera_offset.y, PLAYING_FIELD_HEIGHT - HEIGHT))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                toggle_resolution()
            if event.key == pygame.K_1: 
                if ship.landed and ship.current_planet and ship.current_planet.is_shop:
                    ship.buy_upgrade('max_fuel')
                else:
                    current_motion_model = motion_newton
            elif event.key == pygame.K_2:
                if ship.landed and ship.current_planet and ship.current_planet.is_shop:
                    ship.buy_upgrade('max_hull')
                else:
                    current_motion_model = motion_buridan
            elif event.key == pygame.K_3:
                if ship.landed and ship.current_planet and ship.current_planet.is_shop:
                    ship.buy_upgrade('thrust')
                else:
                    current_motion_model = motion_aristotle
            elif event.key == pygame.K_4 and ship.landed and ship.current_planet and ship.current_planet.is_shop:
                ship.buy_upgrade('shoot_delay')
            elif event.key == pygame.K_5 and ship.landed and ship.current_planet and ship.current_planet.is_shop:
                ship.buy_upgrade('oxygen_efficiency')

    if not (ship.landed and ship.current_planet and ship.current_planet.is_shop):
        for body in all_bodies:
            body.motion_model = current_motion_model
            body.impetus = pygame.Vector2(0, 0)

    # Input reading
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT]: ship.rotate(-1)
    if keys[pygame.K_RIGHT]: ship.rotate(1)
    if keys[pygame.K_UP]: ship.apply_thrust()
    else: ship.stop_thrust()
    if keys[pygame.K_z]: ship.thrust_force = max(ship.thrust_force_min, ship.thrust_force - ship.thrust_force_step)
    if keys[pygame.K_x]: ship.thrust_force = min(ship.thrust_force_max, ship.thrust_force + ship.thrust_force_step)
    if keys[pygame.K_SPACE]: ship.shoot()
    if keys[pygame.K_g]:
        ship.fuel = ship.max_fuel
        ship.oxygen = 100
        ship.hull = ship.max_hull

    for body in all_bodies:
        body.update()

    if ship.oxygen <= 0:
        if oxygen_depletion_time is None:
            oxygen_depletion_time = pygame.time.get_ticks()
        elif pygame.time.get_ticks() - oxygen_depletion_time >= 5000:
            game_over = True
    else:
        oxygen_depletion_time = None

    if ship.hull <= 0:
        game_over = True

    if ship.position.distance_to(goal_planet.position) < goal_planet.radius + ship.radius:
        generate_new_level()
        continue

    if isinstance(current_motion_model, AristotelianMotion):
        for body in all_bodies:
            body.thrusting = False
            body.acceleration = pygame.Vector2(0, 0)

    closest_planet = min(
        (planet for planet in planets if planet != ship.current_planet and not planet.harvested and planet != starting_planet),
        key=lambda planet: ship.position.distance_to(planet.position),
        default=None
    )

    arrow_start = ship.position - camera_offset
    arrow_end = closest_planet.position - camera_offset if closest_planet else arrow_start

    if closest_planet and ship.position != closest_planet.position:
        draw_arrow(screen, arrow_start, arrow_end, (255, 255, 0))

    for projectile in ship.projectiles[:]:
        for body in all_bodies:
            if body != ship:
                if projectile.position.distance_to(body.position) < projectile.radius + body.radius:
                    projectile.lifetime = 0
                    if isinstance(body, EnemyShip):
                        body.hull -= projectile.damage
                        if body.hull <= 0:
                            if body in all_bodies:
                                all_bodies.remove(body)
                            if body in enemy_ships:
                                enemy_ships.remove(body)
                    break

    # Collision detection

    for i, a in enumerate(all_bodies):
        for j, b in enumerate(all_bodies):
            if i >= j: continue
            if a.check_collision(b):
                if (isinstance(a, EnemyShip) and isinstance(b, Ship)):
                    b.take_damage(a.velocity.length())
                    all_bodies.remove(a)
                    continue
                if (isinstance(b, EnemyShip) and isinstance(a, Ship)):
                    a.take_damage(b.velocity.length())
                    all_bodies.remove(b)
                    continue

                if isinstance(a, Asteroid) or isinstance(b, Asteroid):
                    if isinstance(a, Ship):
                        a.take_damage(1) # Dont know whats up with  this but it does a lot more damage than it should
                    if isinstance(b, Ship):
                        b.take_damage(1)
                    if isinstance(a, Asteroid):
                        all_bodies.remove(a)
                    if isinstance(b, Asteroid):
                        all_bodies.remove(b)
                    continue 

                if isinstance(a, Ship) and isinstance(b, Planet) and not a.landed:
                    delta = b.position - a.position
                    direction = delta.normalize()
                    ship_bottom_direction = pygame.Vector2(-math.sin(math.radians(a.angle)), math.cos(math.radians(a.angle)))
                    alignment = ship_bottom_direction.dot(direction)
                    distance_to_surface = delta.length() - (a.radius + b.radius)
                    if abs(distance_to_surface) < 10 and alignment > 0.75:
                        a.land(b)
                elif isinstance(b, Ship) and isinstance(a, Planet) and not b.landed:
                    delta = a.position - b.position
                    direction = delta.normalize()
                    ship_bottom_direction = pygame.Vector2(-math.sin(math.radians(b.angle)), math.cos(math.radians(b.angle)))
                    alignment = ship_bottom_direction.dot(direction)
                    distance_to_surface = delta.length() - (a.radius + b.radius)
                    if abs(distance_to_surface) < 10 and alignment > 0.75:
                        b.land(a)

                delta = b.position - a.position
                direction = delta.normalize() if delta.length_squared() != 0 else pygame.Vector2(1, 0)
                overlap = (a.radius + b.radius) - delta.length()
                if overlap > 0:
                    correction = direction * (overlap / 2)
                    if not isinstance(a, Planet):
                        a.position -= correction
                    if not isinstance(b, Planet):
                        b.position += correction

                rel_vel = b.velocity - a.velocity
                vel_along_normal = rel_vel.dot(direction)
                if vel_along_normal <= 0:
                    if isinstance(current_motion_model, (NewtonianMotion, BuridanMotion)):
                        impulse_mag = (4 * vel_along_normal) / (a.mass + b.mass)
                        impulse = impulse_mag * direction
                        if not isinstance(a, Planet):
                            a.velocity += impulse * b.mass
                        if not isinstance(b, Planet):
                            b.velocity -= impulse * a.mass
                        collision_force = abs(vel_along_normal)
                        if isinstance(a, Ship):
                            a.take_damage(collision_force)
                        if isinstance(b, Ship):
                            b.take_damage(collision_force)
                        if isinstance(a, Ship):
                            a.rotate(random.choice([-1, 1]) * random.randint(5, 15))
                        if isinstance(b, Ship):
                            b.rotate(random.choice([-1, 1]) * random.randint(5, 15))

    if ship.landed and keys[pygame.K_UP]:
        ship.take_off()
    elif keys[pygame.K_UP]:
        ship.apply_thrust()
    else:
        ship.stop_thrust()

    for star_pos in stars:
        screen_pos = star_pos - (camera_offset * 0.25)
        if 0 <= screen_pos.x <= WIDTH and 0 <= screen_pos.y <= HEIGHT:
            pygame.draw.circle(screen, (255, 255, 255), (int(screen_pos.x), int(screen_pos.y)), 1)

    for body in all_bodies:
        body.draw(screen, camera_offset)

    if ship.velocity.length_squared() > 0:
        vel_end = VEC_ORIGIN + ship.velocity * VEC_SCALE
        pygame.draw.line(screen, (0, 0, 255), VEC_ORIGIN, vel_end, 2)
        pygame.draw.circle(screen, (0, 0, 255), (int(vel_end.x), int(vel_end.y)), 3)

    if ship.net_acceleration.length_squared() > 0:
        acc_end = VEC_ORIGIN + ship.net_acceleration * VEC_SCALE * 5
        pygame.draw.line(screen, (255, 0, 0), VEC_ORIGIN, acc_end, 2)
        pygame.draw.circle(screen, (255, 0, 0), (int(acc_end.x), int(acc_end.y)), 3)

    # note that the units here are pixels and frames
    font = pygame.font.SysFont(None, 24)
    screen.blit(font.render(f"Thrust: {ship.thrust_force}", True, (255, 255, 255)), (10, 10))
    screen.blit(font.render("Vel", True, (0, 0, 255)), (VEC_ORIGIN.x + 5, VEC_ORIGIN.y - 20))
    screen.blit(font.render("Acc", True, (255, 0, 0)), (VEC_ORIGIN.x + 5, VEC_ORIGIN.y))
    vel_text = font.render(f"V=({ship.velocity.x:.2f}, {ship.velocity.y:.2f})", True, (0, 0, 255))
    acc_text = font.render(f"A=({ship.net_acceleration.x:.2f}, {ship.net_acceleration.y:.2f})", True, (255, 0, 0))
    screen.blit(vel_text, (VEC_ORIGIN.x - 150, VEC_ORIGIN.y - 40))
    screen.blit(acc_text, (VEC_ORIGIN.x - 150, VEC_ORIGIN.y - 20))

    screen.blit(font.render(f"Fuel: {ship.fuel:.2f}%", True, (255, 255, 255)), (10, 40))
    screen.blit(font.render(f"Oxygen: {ship.oxygen:.2f}%", True, (255, 255, 255)), (10, 60))
    screen.blit(font.render(f"Hull: {ship.hull:.2f}%", True, (255, 255, 255)), (10, 80))
    screen.blit(font.render(f"Cash: {ship.cash:.2f}", True, (255, 215, 0)), (10, 100))

    physics_text = "Physics: "
    if current_motion_model == motion_newton:
        physics_text += "Newtonian"
    elif current_motion_model == motion_buridan:
        physics_text += "Buridan"
    else:
        physics_text += "Aristotelian"
    physics_label = font.render(physics_text, True, (255, 255, 255))
    screen.blit(physics_label, (WIDTH - physics_label.get_width() - 10, 10))

    draw_compass(screen, ship.position, goal_planet.position)

    

    if ship.landed and ship.current_planet and ship.current_planet.is_shop:
        y = HEIGHT // 2
        font = pygame.font.SysFont(None, 24)
        x = 10
        screen.blit(font.render("Shop Upgrades:", True, (218, 165, 32)), (x, y))
        y += 25
        for i, (upgrade, (cost, amount)) in enumerate(ship.current_planet.upgrades.items()):
            txt = f"{i+1}: {upgrade} (+{amount}) - ${cost}"
            screen.blit(font.render(txt, True, (255, 255, 255)), (x, y))
            y += 20

    upgrade_info = [
        f"Max Fuel: {ship.max_fuel}",
        f"Max Hull: {ship.max_hull}",
        f"Max Thrust: {ship.thrust_force_max}",
        f"Shoot Delay: {ship.shoot_delay} frames",
        f"O2 Use: {ship.oxygen_depletion_rate:.3f}/s"
    ]
    upgrade_font = pygame.font.SysFont(None, 22)
    upgrade_y = HEIGHT - 100
    for line in upgrade_info:
        screen.blit(upgrade_font.render(line, True, (173, 216, 230)), (10, upgrade_y))
        upgrade_y += 20

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
