# CORAL licensing status: unresolved

CORAL (the LCG Common Relational Abstraction Layer) is CERN software from the LCG Persistency
Framework. Neither the CMS fork that this recipe builds
(https://github.com/cms-externals/coral, branch `cms/CORAL_2_3_21py3`) nor the upstream
repository (https://gitlab.cern.ch/lcgcoral/coral) contains a LICENSE file, and the source
files carry no license headers.

This recipe therefore cannot be submitted to conda-forge yet. The licence has to be clarified
with the CERN LCG/Persistency maintainers and with CMS, in the same way as for the `utm`
package. Until then this recipe is only built locally.
