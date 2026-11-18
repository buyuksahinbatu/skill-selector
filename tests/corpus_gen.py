from __future__ import annotations

import random

from helpers import write_skill

COMMON_WORDS = """fix test page update code file build run review create add check error data app api
user project config deploy write read component function design style server client database query
performance security document report plan debug refactor migrate install setup generate analyze
optimize validate format search list export import convert release version branch commit merge
issue feature module package script""".split()

MID_WORDS_REAL = """login readme section header footer settings modal unit service variable signup form
email input sidebar mobile csv console changelog color button pagination dropdown table staging
password upload download cache session cookie route navbar tooltip avatar filter checkbox toggle
theme layout grid font icon image link redirect timeout retry queue worker cron log metric alert
chart calendar notification keyboard locale currency""".split()
MID_WORDS = MID_WORDS_REAL + ["term%03d" % i for i in range(400 - len(MID_WORDS_REAL))]

TARGETS = [  # (name, description, prompt)
 ("quartz-invoice-reconciler", "Reconcile supplier invoices against ledger entries and flag mismatched VAT totals.", "reconcile these supplier invoices with the ledger"),
 ("kubernetes-pod-eviction", "Diagnose Kubernetes pod evictions, OOMKilled containers and node pressure events.", "why do my kubernetes pods keep getting evicted"),
 ("stripe-webhook-signature", "Verify Stripe webhook signatures and replay failed webhook deliveries safely.", "verify the stripe webhook signature in this handler"),
 ("latex-thesis-formatter", "Format a LaTeX thesis: bibliography, figure captions, margins and chapter numbering.", "fix the bibliography and margins in my latex thesis"),
 ("postgres-vacuum-tuning", "Tune Postgres autovacuum, find table bloat and dead tuples.", "postgres table bloat is growing, tune autovacuum"),
 ("figma-token-export", "Export Figma design tokens to CSS variables and Tailwind theme files.", "export figma tokens to tailwind"),
 ("ios-provisioning-profile", "Repair iOS provisioning profiles, signing certificates and entitlements for TestFlight.", "testflight upload fails because of the provisioning profile"),
 ("terraform-state-surgery", "Move, import and remove resources in Terraform state without destroying infrastructure.", "move this resource in terraform state without destroying it"),
 ("gdpr-erasure-request", "Handle GDPR erasure requests: locate personal data, anonymize records, log the deletion.", "handle a gdpr erasure request for this customer"),
 ("shopify-liquid-snippets", "Write Shopify Liquid snippets and sections for storefront themes.", "write a liquid snippet for the shopify storefront"),
 ("dicom-anonymizer", "Strip patient identifiers from DICOM medical imaging headers.", "anonymize the patient identifiers in these dicom files"),
 ("ffmpeg-subtitle-burn", "Burn subtitles into video with ffmpeg and fix subtitle timing drift.", "burn the subtitles into this video with ffmpeg"),
 ("graphql-schema-stitching", "Stitch GraphQL schemas across services and resolve federation conflicts.", "stitch these graphql schemas together"),
 ("arduino-sensor-calibration", "Calibrate Arduino temperature and humidity sensors and smooth noisy readings.", "calibrate the humidity sensor on my arduino"),
 ("excel-pivot-forecast", "Build Excel pivot tables and seasonal forecast sheets from sales exports.", "make a pivot table and forecast from this excel sales export"),
 ("kafka-consumer-lag", "Investigate Kafka consumer lag, rebalance storms and partition skew.", "kafka consumer lag keeps growing on one partition"),
 ("wordpress-woocommerce-checkout", "Customize the WooCommerce checkout: fields, shipping zones and tax display.", "add a custom field to the woocommerce checkout"),
 ("unity-shader-graph", "Author Unity Shader Graph materials: dissolve, outline and water effects.", "make a dissolve effect in unity shader graph"),
 ("sourdough-hydration", "Calculate sourdough hydration, starter ratios and proofing schedules.", "calculate hydration for a sourdough loaf"),
 ("oauth-pkce-flow", "Implement the OAuth PKCE authorization flow with refresh token rotation.", "implement oauth pkce login with refresh token rotation"),
]

ORDINARY_PROMPTS = [
 "fix the failing test on the login page",
 "update the readme and add an install section",
 "why is this function returning undefined",
 "refactor this module to be easier to read",
 "add a button to the header that opens the settings modal",
 "the build is broken after the last merge, can you check",
 "write unit tests for the user service",
 "rename this variable everywhere in the project",
 "review my last commit before I push",
 "the page loads slowly, find out why",
 "add validation to the signup form email input",
 "clean up the unused imports in this file",
 "make the sidebar collapse on mobile",
 "create a script that exports the data to csv",
 "there is an error in the console when I click save",
 "bump the version and write the changelog",
 "change the color of the primary button to blue",
 "add pagination and a sort dropdown to the table",
 "deploy the latest branch to staging",
 "explain what this code does step by step",
]


def generate_corpus(root, n=2000, seed=1234):
    rng = random.Random(seed)
    for i in range(n):
        name = "-".join(rng.choices(COMMON_WORDS, k=2)) + "-%04d" % i
        words = rng.choices(COMMON_WORDS, k=rng.randint(14, 22)) + rng.choices(MID_WORDS, k=3)
        rng.shuffle(words)
        write_skill(root, name, " ".join(words), " ".join(rng.choices(COMMON_WORDS, k=40)))


def write_targets(root):
    for name, description, _ in TARGETS:
        write_skill(root, name, description)
