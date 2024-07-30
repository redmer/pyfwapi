import enum


class Ranged(enum.StrEnum):
    """Ranged predicates allow ranged values"""

    FileModification = "mt"
    IPTCCreationTime = "it"
    ReleasedTime = "rt"
    CameraTime = "ct"
    FileSize = "fs"
    PixelHeight = "ph"
    PixelWidth = "pw"


class StrSpecial(enum.StrEnum):
    """Special predicates map to special file propeties"""

    FileName = "fn"
    DirectoryName = "dn"
    FullFilePath = "fp"
    AssetType = "dt"
    ImageOrientation = "o"
    ColorSpace = "cs"
