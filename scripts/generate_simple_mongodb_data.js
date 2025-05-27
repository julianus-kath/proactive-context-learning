// MongoDB data generation script
// This script generates sample data for MongoDB collections

// Sample product and customer IDs
const SAMPLE_PRODUCT_IDS = Array.from({length: 100}, (_, i) => `PROD-${String(i+1).padStart(4, '0')}`);
const SAMPLE_CUSTOMER_IDS = Array.from({length: 50}, (_, i) => `CUST-${String(i+1).padStart(4, '0')}`);

// Connect to the database
const conn = new Mongo();
const db = conn.getDB("document_store");

// Drop existing collections
db.product_details.drop();
db.customer_feedback.drop();
db.support_tickets.drop();
db.knowledge_base.drop();

// Generate product details
print("Generating product details...");
const productDetails = [];

for (let i = 0; i < 50; i++) {
    const productId = SAMPLE_PRODUCT_IDS[i];
    
    productDetails.push({
        product_id: productId,
        detailed_description: `Detailed description for product ${productId}`,
        specifications: {
            dimensions: {
                length: Math.random() * 100,
                width: Math.random() * 100,
                height: Math.random() * 100,
                unit: ["cm", "mm", "inches"][Math.floor(Math.random() * 3)]
            },
            weight: {
                value: Math.random() * 50,
                unit: ["kg", "g", "lbs"][Math.floor(Math.random() * 3)]
            },
            materials: Array.from({length: Math.floor(Math.random() * 4) + 1}, (_, j) => `Material ${j+1}`),
            colors: Array.from({length: Math.floor(Math.random() * 3) + 1}, (_, j) => `Color ${j+1}`)
        },
        features: Array.from({length: Math.floor(Math.random() * 5) + 3}, (_, j) => `Feature ${j+1}`),
        benefits: Array.from({length: Math.floor(Math.random() * 3) + 2}, (_, j) => `Benefit ${j+1}`),
        usage_instructions: `Usage instructions for product ${productId}`,
        warranty_info: {
            duration: [1, 2, 3, 5, 10][Math.floor(Math.random() * 5)],
            coverage: `Warranty coverage for product ${productId}`,
            limitations: `Warranty limitations for product ${productId}`
        },
        media: {
            images: Array.from({length: Math.floor(Math.random() * 5) + 2}, (_, j) => `product_${productId}_image_${j+1}.jpg`),
            videos: Array.from({length: Math.floor(Math.random() * 2) + 1}, (_, j) => `product_${productId}_video_${j+1}.mp4`),
            documents: Array.from({length: Math.floor(Math.random() * 2) + 1}, (_, j) => `product_${productId}_doc_${j+1}.pdf`)
        },
        related_products: SAMPLE_PRODUCT_IDS.filter(pid => pid !== productId).slice(0, Math.floor(Math.random() * 5)),
        metadata: {
            created_at: new Date(Date.now() - Math.random() * 730 * 24 * 60 * 60 * 1000).toISOString(),
            updated_at: new Date(Date.now() - Math.random() * 180 * 24 * 60 * 60 * 1000).toISOString(),
            created_by: `user${Math.floor(Math.random() * 100) + 1}@example.com`,
            version: `${Math.floor(Math.random() * 5) + 1}.${Math.floor(Math.random() * 10)}`
        }
    });
}

// Insert product details
db.product_details.insertMany(productDetails);
print(`Inserted ${productDetails.length} product details`);

// Generate customer feedback
print("Generating customer feedback...");
const customerFeedback = [];

for (let i = 0; i < 100; i++) {
    const sentiments = ["positive", "neutral", "negative"];
    const sentiment = sentiments[Math.floor(Math.random() * sentiments.length)];
    
    let rating;
    if (sentiment === "negative") {
        rating = Math.floor(Math.random() * 5) + 1;
    } else if (sentiment === "neutral") {
        rating = Math.floor(Math.random() * 2) + 3;
    } else {
        rating = Math.floor(Math.random() * 2) + 4;
    }
    
    const feedbackDate = new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000);
    
    customerFeedback.push({
        feedback_id: `FEED-${String(i+1).padStart(4, '0')}`,
        customer_id: SAMPLE_CUSTOMER_IDS[Math.floor(Math.random() * SAMPLE_CUSTOMER_IDS.length)],
        product_id: SAMPLE_PRODUCT_IDS[Math.floor(Math.random() * SAMPLE_PRODUCT_IDS.length)],
        rating: rating,
        sentiment: sentiment,
        title: `Feedback title ${i+1}`,
        content: `Feedback content ${i+1} with ${rating > 3 ? 'positive' : 'negative'} sentiment.`,
        feedback_date: feedbackDate.toISOString(),
        purchase_verified: Math.random() < 0.75,
        helpful_votes: Math.floor(Math.random() * 100),
        media: {
            images: Array.from({length: Math.floor(Math.random() * 3)}, (_, j) => `feedback_image_${j+1}.jpg`)
        },
        tags: ["quality", "price", "delivery", "service", "durability", "design", "functionality", "ease of use"]
            .sort(() => 0.5 - Math.random()).slice(0, Math.floor(Math.random() * 4)),
        response: {
            has_response: Math.random() < 0.7,
            response_date: Math.random() < 0.7 ? new Date(feedbackDate.getTime() + Math.random() * 14 * 24 * 60 * 60 * 1000).toISOString() : null,
            response_content: Math.random() < 0.7 ? `Response to feedback ${i+1}` : null,
            responder: Math.random() < 0.7 ? `Support Agent ${Math.floor(Math.random() * 10) + 1}` : null
        }
    });
}

// Insert customer feedback
db.customer_feedback.insertMany(customerFeedback);
print(`Inserted ${customerFeedback.length} customer feedback documents`);

// Generate support tickets
print("Generating support tickets...");
const supportTickets = [];

const ticketTypes = ["technical_issue", "billing_inquiry", "product_question", "return_request", "complaint"];
const priorities = ["low", "medium", "high", "critical"];
const statuses = ["open", "in_progress", "waiting_on_customer", "waiting_on_third_party", "resolved", "closed"];

for (let i = 0; i < 100; i++) {
    const createdDate = new Date(Date.now() - Math.random() * 365 * 24 * 60 * 60 * 1000);
    
    const status = statuses[Math.floor(Math.random() * statuses.length)];
    let resolution = null;
    let resolvedDate = null;
    let satisfactionRating = null;
    
    if (status === "resolved" || status === "closed") {
        resolution = {
            resolution_type: ["fixed", "workaround", "not_reproducible", "by_design", "no_fix_required"][Math.floor(Math.random() * 5)],
            resolution_note: `Resolution note for ticket ${i+1}`
        };
        resolvedDate = new Date(createdDate.getTime() + Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString();
        satisfactionRating = Math.floor(Math.random() * 5) + 1;
    }
    
    supportTickets.push({
        ticket_id: `TCKT-${String(i+1).padStart(4, '0')}`,
        customer_id: SAMPLE_CUSTOMER_IDS[Math.floor(Math.random() * SAMPLE_CUSTOMER_IDS.length)],
        product_id: SAMPLE_PRODUCT_IDS[Math.floor(Math.random() * SAMPLE_PRODUCT_IDS.length)],
        subject: `Ticket subject ${i+1}`,
        description: `Ticket description ${i+1}`,
        type: ticketTypes[Math.floor(Math.random() * ticketTypes.length)],
        priority: priorities[Math.floor(Math.random() * priorities.length)],
        status: status,
        created_at: createdDate.toISOString(),
        updated_at: new Date(createdDate.getTime() + Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
        resolution: resolution,
        resolved_at: resolvedDate,
        satisfaction_rating: satisfactionRating,
        attachments: Array.from({length: Math.floor(Math.random() * 2)}, (_, j) => `ticket_${i+1}_attachment_${j+1}.pdf`),
        tags: ["hardware", "software", "billing", "shipping", "returns", "warranty", "damage", "missing_parts"]
            .sort(() => 0.5 - Math.random()).slice(0, Math.floor(Math.random() * 3)),
        notes: Array.from({length: Math.floor(Math.random() * 5)}, (_, j) => ({
            timestamp: new Date(createdDate.getTime() + j * 24 * 60 * 60 * 1000 + Math.random() * 8 * 60 * 60 * 1000).toISOString(),
            author: `Agent ${Math.floor(Math.random() * 10) + 1}`,
            content: `Note ${j+1} for ticket ${i+1}`,
            internal: Math.random() < 0.5
        }))
    });
}

// Insert support tickets
db.support_tickets.insertMany(supportTickets);
print(`Inserted ${supportTickets.length} support tickets`);

// Generate knowledge base articles
print("Generating knowledge base articles...");
const knowledgeBase = [];

const categories = ["troubleshooting", "how-to", "faq", "product-info", "policy"];

for (let i = 0; i < 30; i++) {
    const createdDate = new Date(Date.now() - Math.random() * 730 * 24 * 60 * 60 * 1000);
    const updatedDate = new Date(createdDate.getTime() + Math.random() * 365 * 24 * 60 * 60 * 1000);
    
    // Select random products this article applies to
    const applicableProducts = SAMPLE_PRODUCT_IDS
        .sort(() => 0.5 - Math.random())
        .slice(0, Math.floor(Math.random() * 10) + 1);
    
    knowledgeBase.push({
        article_id: `KB-${String(i+1).padStart(4, '0')}`,
        title: `Knowledge Base Article ${i+1}`,
        category: categories[Math.floor(Math.random() * categories.length)],
        content: `Content for knowledge base article ${i+1}. This is a detailed explanation.`,
        applicable_products: applicableProducts,
        tags: ["setup", "installation", "troubleshooting", "maintenance", "repair", "warranty", "returns", "usage"]
            .sort(() => 0.5 - Math.random()).slice(0, Math.floor(Math.random() * 3) + 1),
        created_at: createdDate.toISOString(),
        updated_at: updatedDate.toISOString(),
        author: `Author ${Math.floor(Math.random() * 10) + 1}`,
        view_count: Math.floor(Math.random() * 10000),
        helpful_rating: Math.floor(Math.random() * 50) / 10 + 1,
        related_articles: Array.from({length: Math.floor(Math.random() * 3)}, () => 
            `KB-${String(Math.floor(Math.random() * 30) + 1).padStart(4, '0')}`)
    });
}

// Insert knowledge base articles
db.knowledge_base.insertMany(knowledgeBase);
print(`Inserted ${knowledgeBase.length} knowledge base articles`);

// Create text indexes on all collections
print("Creating text indexes on collections...");

// Product details text index
db.product_details.createIndex(
    { 
        product_id: "text",
        detailed_description: "text",
        "specifications.materials": "text",
        "specifications.colors": "text",
        features: "text",
        benefits: "text",
        usage_instructions: "text",
        "warranty_info.coverage": "text",
        "warranty_info.limitations": "text"
    },
    { name: "product_details_text_index" }
);
print("Created text index on product_details collection");

// Customer feedback text index
db.customer_feedback.createIndex(
    {
        feedback_id: "text",
        customer_id: "text",
        product_id: "text",
        sentiment: "text",
        title: "text",
        content: "text",
        tags: "text",
        "response.response_content": "text"
    },
    { name: "customer_feedback_text_index" }
);
print("Created text index on customer_feedback collection");

// Support tickets text index
db.support_tickets.createIndex(
    {
        ticket_id: "text",
        customer_id: "text",
        product_id: "text",
        subject: "text",
        description: "text",
        type: "text",
        priority: "text",
        status: "text",
        tags: "text",
        "notes.content": "text",
        "resolution.resolution_note": "text"
    },
    { name: "support_tickets_text_index" }
);
print("Created text index on support_tickets collection");

// Knowledge base text index
db.knowledge_base.createIndex(
    {
        article_id: "text",
        title: "text",
        category: "text",
        content: "text",
        applicable_products: "text",
        tags: "text",
        author: "text"
    },
    { name: "knowledge_base_text_index" }
);
print("Created text index on knowledge_base collection");

// Create regular indexes for common query fields
db.product_details.createIndex({ product_id: 1 });
db.customer_feedback.createIndex({ product_id: 1 });
db.customer_feedback.createIndex({ customer_id: 1 });
db.support_tickets.createIndex({ product_id: 1 });
db.support_tickets.createIndex({ customer_id: 1 });
db.support_tickets.createIndex({ status: 1 });
db.knowledge_base.createIndex({ applicable_products: 1 });
db.knowledge_base.createIndex({ category: 1 });

print("MongoDB data generation and indexing completed successfully!");