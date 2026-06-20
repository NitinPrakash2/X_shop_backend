# Wrapper module to re-export 706 models with a valid Python module name
# This allows scheduler and other code to import models using a standard import instead of importlib

import sys
import os
import importlib.util

# Load the actual 706 module if not already loaded
if "xshop_706_module" not in sys.modules:
    module_path = os.path.join(os.path.dirname(__file__), "706", "index.py")
    spec = importlib.util.spec_from_file_location("xshop_706_module", module_path)
    _706_mod = importlib.util.module_from_spec(spec)
    sys.modules["xshop_706_module"] = _706_mod
    spec.loader.exec_module(_706_mod)
else:
    _706_mod = sys.modules["xshop_706_module"]

# Re-export all models and functions
Seller = _706_mod.Seller
SellerProfile = _706_mod.SellerProfile
Store = _706_mod.Store
XAccount = _706_mod.XAccount
OAuthToken = _706_mod.OAuthToken
Product = _706_mod.Product
ProductSyncLog = _706_mod.ProductSyncLog
PublishJob = _706_mod.PublishJob
Order = _706_mod.Order
AnalyticsEvent = _706_mod.AnalyticsEvent
SellerRefreshToken = _706_mod.SellerRefreshToken
PublishedPost = _706_mod.PublishedPost
SchedulerJob = _706_mod.SchedulerJob
index = _706_mod.index

__all__ = [
    'Seller', 'SellerProfile', 'Store', 'XAccount', 'OAuthToken',
    'Product', 'ProductSyncLog', 'PublishJob', 'Order', 'AnalyticsEvent',
    'SellerRefreshToken', 'PublishedPost', 'SchedulerJob', 'index'
]
