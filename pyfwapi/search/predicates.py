import enum


class Ranged(enum.StrEnum):
    FileModification = "mt"
    IPTCCreationTime = "it"
    ReleasedTime = "rt"
    CameraTime = "ct"
    FileSize = "fs"
    PixelHeight = "ph"
    PixelWidth = "pw"


class StrSpecial(enum.StrEnum):
    FileName = "fn"
    DirectoryName = "dn"
    FullFilePath = "fp"
    AssetType = "dt"
    ImageOrientation = "o"
    ColorSpace = "cs"
