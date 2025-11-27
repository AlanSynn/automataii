#!/usr/bin/env python3
from automataii.application.mechanism_foundry import MechanismFoundryController
from automataii.application.mechanism_transfer import TransferValidationError

controller = MechanismFoundryController()

print("Available mechanisms:")
for item in controller.list_mechanisms():
    print(f"  - {item.display_name} ({item.mechanism_type})")

print(f"\nSelected: {controller.selected_entry.name if controller.selected_entry else 'None'}")

params = controller.initial_parameters()
print(f"Parameters: {params}")

try:
    package = controller.export_mechanism_to_design(
        parameters=params,
        pivot_point=(400.0, 300.0),
    )
    print(f"\n✓ Export successful!")
    print(f"  Type: {package.export_data.mechanism_type}")
    print(f"  Pivot: {package.export_data.visual_config.pivot_point}")
    print(f"  Parameters: {package.export_data.parameters}")
except TransferValidationError as e:
    print(f"\n✗ Export failed: {e}")
