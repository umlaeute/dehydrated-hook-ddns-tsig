#!/bin/sh

UPSTREAM=$(egrep "^upstream-branch" debian/gbp.conf | sed -e 's|.*= *||' -e 's| ||g' | tail -1)
if [ "x${UPSTREAM}" = "x" ]; then
  echo "no upstream branch found in debian/gbp.conf" 1>&2
  exit 1
fi

=20161215.0
date=$(date +%Y%m%d)
i=0
while git tag -l "upstream/0.0_${date}.${i}" | grep . >/dev/null
do
 i=$((i+1))
done

VERSION="0.0_${date}.${i}"
TARBALL="../dehydrated-dnspython-hook_${VERSION}.tar.gz"

git archive -v \
	--format tar.gz \
	-o "${TARBALL}" \
	--prefix=dehydrated-dnspython-hook_${VERSION}/ \
	"${UPSTREAM}" \
&& pristine-tar commit "${TARBALL}" \
&& git tag -m "imported upstream-pseudoversion ${VERSION}" "upstream/${VERSION}" "${UPSTREAM}"  \
&& git merge "${UPSTREAM}" \
${nop}
