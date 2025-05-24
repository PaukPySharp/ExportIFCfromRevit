# -*- coding: utf-8 -*-
import clr
clr.AddReference("RevitAPI")

from Autodesk.Revit import DB
from Autodesk.Revit.DB import FilteredElementCollector as FEC


def search_view3D_navisworks(doc: DB.Document) -> DB.View3D | None:
    # пытаемся найти 3D вид Navisworks
    view_navis = [i for i in FEC(doc).OfClass(DB.View3D)
                  if i.Name == 'Navisworks' and
                  not i.IsTemplate]

    if view_navis:
        return view_navis[0]
    return None
