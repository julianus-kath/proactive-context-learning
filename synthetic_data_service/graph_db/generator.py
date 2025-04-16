"""
Generator for synthetic graph data.
"""

import json
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from faker import Faker

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class GraphGenerator:
    """Generator for synthetic graph data."""

    def __init__(self, seed: Optional[int] = None):
        """Initialize the graph generator.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.seed = seed if seed is not None else random.randint(1, 10000)
        self.faker = Faker()
        self.faker.seed_instance(self.seed)
        random.seed(self.seed)
        
    def generate_employee_network(self, employee_ids: List[int], 
                                 employee_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate employee social network graph.
        
        Args:
            employee_ids: List of employee IDs from the relational database
            employee_data: List of employee data dictionaries with department and position info
            
        Returns:
            Dictionary with nodes and edges for the employee network
        """
        logger.info(f"Generating employee network graph...")
        
        # Create nodes for each employee
        nodes = []
        for i, emp in enumerate(employee_data):
            node = {
                "id": f"employee-{emp['employee_id']}",
                "labels": ["Employee"],
                "properties": {
                    "employee_id": emp["employee_id"],
                    "name": f"{emp['first_name']} {emp['last_name']}",
                    "department": emp["department"],
                    "position": emp["position"],
                    "hire_date": emp["hire_date"],
                    "email": emp["email"]
                }
            }
            nodes.append(node)
        
        # Create edges for relationships
        edges = []
        
        # 1. Manager relationships (already in the relational data)
        for emp in employee_data:
            if emp.get("manager_id"):
                # Parse the hire date string to datetime object
                try:
                    hire_date = datetime.fromisoformat(emp["hire_date"].replace(" ", "T"))
                except ValueError:
                    # Handle different date formats
                    hire_date = datetime.strptime(emp["hire_date"].split(".")[0], "%Y-%m-%d %H:%M:%S")
                
                edge = {
                    "id": f"manages-{emp['manager_id']}-{emp['employee_id']}",
                    "type": "MANAGES",
                    "source": f"employee-{emp['manager_id']}",
                    "target": f"employee-{emp['employee_id']}",
                    "properties": {
                        "since": self.faker.date_time_between(
                            start_date=hire_date, 
                            end_date="now"
                        ).isoformat()
                    }
                }
                edges.append(edge)
        
        # 2. Department colleagues
        departments = {}
        for emp in employee_data:
            dept = emp["department"]
            if dept not in departments:
                departments[dept] = []
            departments[dept].append(emp["employee_id"])
        
        for dept, members in departments.items():
            # Create "WORKS_WITH" relationships between department members
            for i in range(len(members)):
                for j in range(i+1, len(members)):
                    # Not all colleagues work directly together
                    if random.random() < 0.7:
                        # Determine collaboration level
                        collaboration_level = random.choice(["low", "medium", "high"])
                        projects_count = random.randint(1, 3) if collaboration_level == "low" else \
                                        random.randint(3, 7) if collaboration_level == "medium" else \
                                        random.randint(7, 15)
                        
                        edge = {
                            "id": f"works_with-{members[i]}-{members[j]}",
                            "type": "WORKS_WITH",
                            "source": f"employee-{members[i]}",
                            "target": f"employee-{members[j]}",
                            "properties": {
                                "collaboration_level": collaboration_level,
                                "projects_count": projects_count,
                                "last_collaboration": self.faker.date_time_between(
                                    start_date="-1y", 
                                    end_date="now"
                                ).isoformat()
                            }
                        }
                        edges.append(edge)
        
        # 3. Cross-department collaborations
        # Create some random cross-department relationships
        for _ in range(int(len(employee_data) * 0.3)):  # Create cross-dept edges for ~30% of employees
            dept1, dept2 = random.sample(list(departments.keys()), 2)
            emp1 = random.choice(departments[dept1])
            emp2 = random.choice(departments[dept2])
            
            # Skip if relationship already exists
            if any(e["source"] == f"employee-{emp1}" and e["target"] == f"employee-{emp2}" for e in edges) or \
               any(e["source"] == f"employee-{emp2}" and e["target"] == f"employee-{emp1}" for e in edges):
                continue
            
            edge = {
                "id": f"collaborates_with-{emp1}-{emp2}",
                "type": "COLLABORATES_WITH",
                "source": f"employee-{emp1}",
                "target": f"employee-{emp2}",
                "properties": {
                    "project_name": f"Project {self.faker.word().capitalize()}",
                    "start_date": self.faker.date_time_between(
                        start_date="-1y", 
                        end_date="-1m"
                    ).isoformat(),
                    "status": random.choice(["active", "completed", "on_hold"])
                }
            }
            edges.append(edge)
        
        # 4. Mentorship relationships
        # Senior employees mentor junior ones
        senior_employees = [emp["employee_id"] for emp in employee_data 
                           if "Senior" in emp["position"] or "Manager" in emp["position"] 
                           or "Director" in emp["position"] or "VP" in emp["position"]]
        
        junior_employees = [emp["employee_id"] for emp in employee_data 
                           if emp["employee_id"] not in senior_employees]
        
        # Each junior employee might have a mentor
        for junior in junior_employees:
            if random.random() < 0.6:  # 60% chance of having a mentor
                mentor = random.choice(senior_employees)
                
                # Skip if mentor is already the manager
                if any(e["type"] == "MANAGES" and e["source"] == f"employee-{mentor}" 
                      and e["target"] == f"employee-{junior}" for e in edges):
                    continue
                
                edge = {
                    "id": f"mentors-{mentor}-{junior}",
                    "type": "MENTORS",
                    "source": f"employee-{mentor}",
                    "target": f"employee-{junior}",
                    "properties": {
                        "since": self.faker.date_time_between(
                            start_date="-2y", 
                            end_date="-1m"
                        ).isoformat(),
                        "focus_areas": random.sample(
                            ["technical_skills", "leadership", "communication", "domain_knowledge", 
                             "career_development", "project_management"],
                            random.randint(1, 3)
                        )
                    }
                }
                edges.append(edge)
        
        logger.info(f"Generated employee network with {len(nodes)} nodes and {len(edges)} edges.")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "graph_type": "employee_network",
                "generated_at": datetime.now().isoformat(),
                "seed": self.seed,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    
    def generate_product_network(self, product_ids: List[int], 
                                product_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate product relationship network.
        
        Args:
            product_ids: List of product IDs from the relational database
            product_data: List of product data dictionaries with category and supplier info
            
        Returns:
            Dictionary with nodes and edges for the product network
        """
        logger.info(f"Generating product relationship network...")
        
        # Create nodes for each product
        nodes = []
        for prod in product_data:
            node = {
                "id": f"product-{prod['product_id']}",
                "labels": ["Product"],
                "properties": {
                    "product_id": prod["product_id"],
                    "name": prod["product_name"],
                    "category": prod["category"],
                    "subcategory": prod["subcategory"],
                    "price": prod["unit_price"],
                    "supplier_id": prod["supplier_id"]
                }
            }
            nodes.append(node)
        
        # Create category nodes
        categories = set(prod["category"] for prod in product_data)
        for category in categories:
            node = {
                "id": f"category-{category.lower().replace(' & ', '_').replace(' ', '_')}",
                "labels": ["Category"],
                "properties": {
                    "name": category,
                    "product_count": sum(1 for prod in product_data if prod["category"] == category)
                }
            }
            nodes.append(node)
        
        # Create edges
        edges = []
        
        # 1. Product to Category relationships
        for prod in product_data:
            category_id = f"category-{prod['category'].lower().replace(' & ', '_').replace(' ', '_')}"
            edge = {
                "id": f"belongs_to-{prod['product_id']}-{category_id}",
                "type": "BELONGS_TO",
                "source": f"product-{prod['product_id']}",
                "target": category_id,
                "properties": {}
            }
            edges.append(edge)
        
        # 2. Related products (products in same category or subcategory)
        for i, prod1 in enumerate(product_data):
            related_count = 0
            for j, prod2 in enumerate(product_data):
                if i != j and (prod1["category"] == prod2["category"] or 
                              prod1["subcategory"] == prod2["subcategory"]):
                    # Limit the number of related products
                    if related_count >= 5 or random.random() > 0.7:
                        continue
                    
                    relation_strength = random.uniform(0.1, 1.0)
                    relation_type = "SIMILAR_TO" if prod1["subcategory"] == prod2["subcategory"] else "RELATED_TO"
                    
                    edge = {
                        "id": f"{relation_type.lower()}-{prod1['product_id']}-{prod2['product_id']}",
                        "type": relation_type,
                        "source": f"product-{prod1['product_id']}",
                        "target": f"product-{prod2['product_id']}",
                        "properties": {
                            "strength": round(relation_strength, 2),
                            "relation_basis": "same_subcategory" if prod1["subcategory"] == prod2["subcategory"] 
                                            else "same_category"
                        }
                    }
                    edges.append(edge)
                    related_count += 1
        
        # 3. Frequently bought together relationships
        # Create some random "FREQUENTLY_BOUGHT_WITH" relationships
        for _ in range(int(len(product_data) * 0.4)):  # Create for ~40% of products
            prod1, prod2 = random.sample(product_data, 2)
            
            # Skip if relationship already exists
            if any(e["source"] == f"product-{prod1['product_id']}" and 
                  e["target"] == f"product-{prod2['product_id']}" and
                  e["type"] == "FREQUENTLY_BOUGHT_WITH" for e in edges):
                continue
            
            edge = {
                "id": f"frequently_bought_with-{prod1['product_id']}-{prod2['product_id']}",
                "type": "FREQUENTLY_BOUGHT_WITH",
                "source": f"product-{prod1['product_id']}",
                "target": f"product-{prod2['product_id']}",
                "properties": {
                    "confidence": round(random.uniform(0.1, 0.9), 2),
                    "support": round(random.uniform(0.01, 0.2), 3),
                    "lift": round(random.uniform(1.1, 5.0), 2)
                }
            }
            edges.append(edge)
        
        # 4. Accessory relationships
        # Some products are accessories for others
        for _ in range(int(len(product_data) * 0.2)):  # Create for ~20% of products
            main_product, accessory = random.sample(product_data, 2)
            
            # Skip if relationship already exists or if accessory is more expensive
            if any(e["source"] == f"product-{accessory['product_id']}" and 
                  e["target"] == f"product-{main_product['product_id']}" and
                  e["type"] == "ACCESSORY_FOR" for e in edges) or \
               accessory["unit_price"] > main_product["unit_price"]:
                continue
            
            edge = {
                "id": f"accessory_for-{accessory['product_id']}-{main_product['product_id']}",
                "type": "ACCESSORY_FOR",
                "source": f"product-{accessory['product_id']}",
                "target": f"product-{main_product['product_id']}",
                "properties": {
                    "compatibility": random.choice(["required", "optional", "enhances"]),
                    "recommendation_score": round(random.uniform(0.1, 1.0), 2)
                }
            }
            edges.append(edge)
        
        logger.info(f"Generated product network with {len(nodes)} nodes and {len(edges)} edges.")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "graph_type": "product_network",
                "generated_at": datetime.now().isoformat(),
                "seed": self.seed,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    
    def generate_customer_product_network(self, customer_ids: List[int], product_ids: List[int],
                                         sales_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate customer-product interaction network.
        
        Args:
            customer_ids: List of customer IDs from the relational database
            product_ids: List of product IDs from the relational database
            sales_data: List of sales data with customer_id, product_id, and other details
            
        Returns:
            Dictionary with nodes and edges for the customer-product network
        """
        logger.info(f"Generating customer-product interaction network...")
        
        # Create nodes for customers and products
        nodes = []
        
        # Customer nodes
        for cust_id in customer_ids:
            node = {
                "id": f"customer-{cust_id}",
                "labels": ["Customer"],
                "properties": {
                    "customer_id": cust_id
                }
            }
            nodes.append(node)
        
        # Product nodes
        for prod_id in product_ids:
            node = {
                "id": f"product-{prod_id}",
                "labels": ["Product"],
                "properties": {
                    "product_id": prod_id
                }
            }
            nodes.append(node)
        
        # Create edges for purchases
        edges = []
        
        # Process sales data to create PURCHASED edges
        for sale in sales_data:
            edge = {
                "id": f"purchased-{sale['customer_id']}-{sale['product_id']}-{sale['sale_id']}",
                "type": "PURCHASED",
                "source": f"customer-{sale['customer_id']}",
                "target": f"product-{sale['product_id']}",
                "properties": {
                    "sale_id": sale["sale_id"],
                    "date": sale["sale_date"],
                    "quantity": sale["quantity"],
                    "amount": sale["total_amount"],
                    "payment_method": sale["payment_method"]
                }
            }
            edges.append(edge)
        
        # Create VIEWED edges (simulating product views that didn't result in purchase)
        # For each customer, generate some product views
        for cust_id in customer_ids:
            # Determine products this customer has purchased
            purchased_products = [sale["product_id"] for sale in sales_data if sale["customer_id"] == cust_id]
            
            # Generate views for some non-purchased products
            non_purchased = [p_id for p_id in product_ids if p_id not in purchased_products]
            
            # Each customer views 2-10 products they didn't purchase
            num_views = min(random.randint(2, 10), len(non_purchased))
            viewed_products = random.sample(non_purchased, num_views)
            
            for prod_id in viewed_products:
                view_count = random.randint(1, 5)
                last_view_date = self.faker.date_time_between(start_date="-6m", end_date="now").isoformat()
                
                edge = {
                    "id": f"viewed-{cust_id}-{prod_id}",
                    "type": "VIEWED",
                    "source": f"customer-{cust_id}",
                    "target": f"product-{prod_id}",
                    "properties": {
                        "view_count": view_count,
                        "last_view_date": last_view_date,
                        "average_view_time_seconds": random.randint(10, 300)
                    }
                }
                edges.append(edge)
        
        # Create ADDED_TO_CART edges (products added to cart but not purchased)
        for cust_id in customer_ids:
            # 50% chance a customer has abandoned cart items
            if random.random() < 0.5:
                # Determine products this customer has purchased
                purchased_products = [sale["product_id"] for sale in sales_data if sale["customer_id"] == cust_id]
                
                # Generate cart additions for some non-purchased products
                non_purchased = [p_id for p_id in product_ids if p_id not in purchased_products]
                
                # Each customer adds 1-3 products to cart without purchasing
                num_cart_adds = min(random.randint(1, 3), len(non_purchased))
                cart_products = random.sample(non_purchased, num_cart_adds)
                
                for prod_id in cart_products:
                    cart_date = self.faker.date_time_between(start_date="-3m", end_date="now").isoformat()
                    
                    edge = {
                        "id": f"added_to_cart-{cust_id}-{prod_id}",
                        "type": "ADDED_TO_CART",
                        "source": f"customer-{cust_id}",
                        "target": f"product-{prod_id}",
                        "properties": {
                            "date": cart_date,
                            "quantity": random.randint(1, 3),
                            "cart_abandoned": True
                        }
                    }
                    edges.append(edge)
        
        # Create RATED edges for some purchases
        for sale in sales_data:
            # 30% chance a customer rates a purchased product
            if random.random() < 0.3:
                rating = random.randint(1, 5)
                rating_date = datetime.fromisoformat(sale["sale_date"]) + timedelta(days=random.randint(7, 60))
                
                edge = {
                    "id": f"rated-{sale['customer_id']}-{sale['product_id']}-{sale['sale_id']}",
                    "type": "RATED",
                    "source": f"customer-{sale['customer_id']}",
                    "target": f"product-{sale['product_id']}",
                    "properties": {
                        "rating": rating,
                        "date": rating_date.isoformat(),
                        "comment": self.faker.paragraph(nb_sentences=1) if random.random() < 0.5 else None
                    }
                }
                edges.append(edge)
        
        logger.info(f"Generated customer-product network with {len(nodes)} nodes and {len(edges)} edges.")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "graph_type": "customer_product_network",
                "generated_at": datetime.now().isoformat(),
                "seed": self.seed,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    
    def generate_supply_chain_network(self, product_ids: List[int], supplier_ids: List[int],
                                     product_data: List[Dict[str, Any]], 
                                     supplier_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate supply chain network.
        
        Args:
            product_ids: List of product IDs from the relational database
            supplier_ids: List of supplier IDs from the relational database
            product_data: List of product data with supplier_id and other details
            supplier_data: List of supplier data with location and other details
            
        Returns:
            Dictionary with nodes and edges for the supply chain network
        """
        logger.info(f"Generating supply chain network...")
        
        # Create nodes
        nodes = []
        
        # Supplier nodes
        for supplier in supplier_data:
            node = {
                "id": f"supplier-{supplier['supplier_id']}",
                "labels": ["Supplier"],
                "properties": {
                    "supplier_id": supplier["supplier_id"],
                    "name": supplier["name"],
                    "country": supplier["country"],
                    "city": supplier["city"]
                }
            }
            nodes.append(node)
        
        # Product nodes
        for product in product_data:
            node = {
                "id": f"product-{product['product_id']}",
                "labels": ["Product"],
                "properties": {
                    "product_id": product["product_id"],
                    "name": product["product_name"],
                    "category": product["category"]
                }
            }
            nodes.append(node)
        
        # Warehouse nodes (create some fictional warehouses)
        warehouse_locations = [
            {"id": 1, "name": "Main Warehouse", "city": "Chicago", "country": "USA"},
            {"id": 2, "name": "East Coast Facility", "city": "New York", "country": "USA"},
            {"id": 3, "name": "West Coast Facility", "city": "Los Angeles", "country": "USA"},
            {"id": 4, "name": "Central Distribution", "city": "Dallas", "country": "USA"},
            {"id": 5, "name": "European Hub", "city": "Amsterdam", "country": "Netherlands"},
            {"id": 6, "name": "Asian Hub", "city": "Singapore", "country": "Singapore"}
        ]
        
        for wh in warehouse_locations:
            node = {
                "id": f"warehouse-{wh['id']}",
                "labels": ["Warehouse"],
                "properties": {
                    "warehouse_id": wh["id"],
                    "name": wh["name"],
                    "city": wh["city"],
                    "country": wh["country"],
                    "capacity": random.randint(5000, 50000)
                }
            }
            nodes.append(node)
        
        # Distribution center nodes
        distribution_centers = [
            {"id": 1, "name": "North Region DC", "city": "Minneapolis", "country": "USA"},
            {"id": 2, "name": "South Region DC", "city": "Atlanta", "country": "USA"},
            {"id": 3, "name": "European DC", "city": "Frankfurt", "country": "Germany"}
        ]
        
        for dc in distribution_centers:
            node = {
                "id": f"distribution_center-{dc['id']}",
                "labels": ["DistributionCenter"],
                "properties": {
                    "dc_id": dc["id"],
                    "name": dc["name"],
                    "city": dc["city"],
                    "country": dc["country"],
                    "throughput": random.randint(1000, 10000)
                }
            }
            nodes.append(node)
        
        # Create edges
        edges = []
        
        # 1. Supplier to Product relationships
        for product in product_data:
            edge = {
                "id": f"supplies-{product['supplier_id']}-{product['product_id']}",
                "type": "SUPPLIES",
                "source": f"supplier-{product['supplier_id']}",
                "target": f"product-{product['product_id']}",
                "properties": {
                    "lead_time_days": random.randint(3, 45),
                    "min_order_quantity": random.randint(10, 1000),
                    "unit_cost": round(product["cost_price"], 2),
                    "contract_start_date": self.faker.date_time_between(
                        start_date="-3y", 
                        end_date="-6m"
                    ).isoformat()
                }
            }
            edges.append(edge)
        
        # 2. Product to Warehouse relationships (inventory)
        for product in product_data:
            # Each product is stored in 1-3 warehouses
            num_warehouses = random.randint(1, 3)
            selected_warehouses = random.sample(warehouse_locations, num_warehouses)
            
            for wh in selected_warehouses:
                edge = {
                    "id": f"stored_in-{product['product_id']}-{wh['id']}",
                    "type": "STORED_IN",
                    "source": f"product-{product['product_id']}",
                    "target": f"warehouse-{wh['id']}",
                    "properties": {
                        "quantity": random.randint(10, 1000),
                        "reorder_level": random.randint(5, 100),
                        "bin_location": f"{random.choice('ABCDE')}-{random.randint(1, 99)}-{random.randint(1, 20)}"
                    }
                }
                edges.append(edge)
        
        # 3. Warehouse to Distribution Center relationships
        for wh in warehouse_locations:
            # Each warehouse supplies 1-2 distribution centers
            num_dcs = random.randint(1, min(2, len(distribution_centers)))
            selected_dcs = random.sample(distribution_centers, num_dcs)
            
            for dc in selected_dcs:
                edge = {
                    "id": f"supplies-{wh['id']}-{dc['id']}",
                    "type": "SUPPLIES",
                    "source": f"warehouse-{wh['id']}",
                    "target": f"distribution_center-{dc['id']}",
                    "properties": {
                        "shipping_frequency": random.choice(["daily", "weekly", "bi-weekly"]),
                        "shipping_method": random.choice(["truck", "rail", "air", "sea"]),
                        "transit_time_days": random.randint(1, 14)
                    }
                }
                edges.append(edge)
        
        # 4. Supplier relationships (some suppliers have relationships with each other)
        for i in range(len(supplier_data)):
            for j in range(i+1, len(supplier_data)):
                # 20% chance that suppliers have a relationship
                if random.random() < 0.2:
                    relationship_type = random.choice(["PARTNERS_WITH", "COMPETES_WITH", "SUBSIDIARY_OF"])
                    
                    # For SUBSIDIARY_OF, determine direction based on random choice
                    if relationship_type == "SUBSIDIARY_OF":
                        if random.random() < 0.5:
                            source_id = supplier_data[i]["supplier_id"]
                            target_id = supplier_data[j]["supplier_id"]
                        else:
                            source_id = supplier_data[j]["supplier_id"]
                            target_id = supplier_data[i]["supplier_id"]
                    else:
                        source_id = supplier_data[i]["supplier_id"]
                        target_id = supplier_data[j]["supplier_id"]
                    
                    edge = {
                        "id": f"{relationship_type.lower()}-{source_id}-{target_id}",
                        "type": relationship_type,
                        "source": f"supplier-{source_id}",
                        "target": f"supplier-{target_id}",
                        "properties": {
                            "established_date": self.faker.date_time_between(
                                start_date="-10y", 
                                end_date="-1y"
                            ).isoformat(),
                            "relationship_strength": random.choice(["weak", "moderate", "strong"])
                        }
                    }
                    edges.append(edge)
        
        logger.info(f"Generated supply chain network with {len(nodes)} nodes and {len(edges)} edges.")
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "graph_type": "supply_chain_network",
                "generated_at": datetime.now().isoformat(),
                "seed": self.seed,
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
    
    def generate_all_graphs(self, employee_data: List[Dict[str, Any]], 
                           product_data: List[Dict[str, Any]],
                           supplier_data: List[Dict[str, Any]],
                           sales_data: List[Dict[str, Any]],
                           output_dir: str) -> Dict[str, Dict[str, int]]:
        """Generate all graph networks and save to JSON files.
        
        Args:
            employee_data: List of employee data from the relational database
            product_data: List of product data from the relational database
            supplier_data: List of supplier data from the relational database
            sales_data: List of sales data from the relational database
            output_dir: Directory to save the generated JSON files
            
        Returns:
            Dictionary with graph names and node/edge counts
        """
        logger.info(f"Generating graph networks with seed {self.seed}...")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract IDs from data
        employee_ids = [emp["employee_id"] for emp in employee_data]
        product_ids = [prod["product_id"] for prod in product_data]
        supplier_ids = [sup["supplier_id"] for sup in supplier_data]
        customer_ids = list(set(sale["customer_id"] for sale in sales_data))
        
        # Generate and save each graph
        graphs = {}
        
        # Employee network
        employee_network = self.generate_employee_network(employee_ids, employee_data)
        with open(os.path.join(output_dir, "employee_network.json"), "w") as f:
            json.dump(employee_network, f, indent=2)
        graphs["employee_network"] = {
            "nodes": len(employee_network["nodes"]),
            "edges": len(employee_network["edges"])
        }
        
        # Product network
        product_network = self.generate_product_network(product_ids, product_data)
        with open(os.path.join(output_dir, "product_network.json"), "w") as f:
            json.dump(product_network, f, indent=2)
        graphs["product_network"] = {
            "nodes": len(product_network["nodes"]),
            "edges": len(product_network["edges"])
        }
        
        # Customer-Product network
        customer_product_network = self.generate_customer_product_network(
            customer_ids, product_ids, sales_data
        )
        with open(os.path.join(output_dir, "customer_product_network.json"), "w") as f:
            json.dump(customer_product_network, f, indent=2)
        graphs["customer_product_network"] = {
            "nodes": len(customer_product_network["nodes"]),
            "edges": len(customer_product_network["edges"])
        }
        
        # Supply Chain network
        supply_chain_network = self.generate_supply_chain_network(
            product_ids, supplier_ids, product_data, supplier_data
        )
        with open(os.path.join(output_dir, "supply_chain_network.json"), "w") as f:
            json.dump(supply_chain_network, f, indent=2)
        graphs["supply_chain_network"] = {
            "nodes": len(supply_chain_network["nodes"]),
            "edges": len(supply_chain_network["edges"])
        }
        
        # Save graph summary
        total_nodes = sum(g["nodes"] for g in graphs.values())
        total_edges = sum(g["edges"] for g in graphs.values())
        
        with open(os.path.join(output_dir, "graphs_summary.json"), "w") as f:
            json.dump({
                "total_nodes": total_nodes,
                "total_edges": total_edges,
                "graphs": graphs,
                "generation_date": datetime.now().isoformat(),
                "seed": self.seed
            }, f, indent=2)
        
        logger.info(f"Generated {len(graphs)} graphs with {total_nodes} nodes and {total_edges} edges total.")
        
        return graphs