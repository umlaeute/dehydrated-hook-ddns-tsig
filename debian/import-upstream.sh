#!/bin/sh

UPSTREAM=$(egrep "^upstream-branch" debian/gbp.conf | sed -e 's|.*= *||' -e 's| ||g' | tail -1)
if [ "x${UPSTREAM}" = "x" ]; then
  echo "no upstream branch found in debian/gbp.conf" 1>&2
  exit 1
fi

version2tag() {
  echo upstream/$1 | sed -e 's|~|_|g'
}

date=$(date +%Y%m%d)
i=0
VERSION="0.0~${date}.${i}"
while git tag -l "$(version2tag ${VERSION})" | grep . >/dev/null
do
 i=$((i+1))
 VERSION="0.0~${date}.${i}"
done

TARBALL="../dehydrated-dnspython-hook_${VERSION}.tar.gz"

git archive -v \
	--format tar.gz \
	-o "${TARBALL}" \
	--prefix=dehydrated-dnspython-hook_${VERSION}/ \
	"${UPSTREAM}" \
&& pristine-tar commit "${TARBALL}" \
&& git tag -m "imported upstream-pseudoversion ${VERSION}" "$(version2tag ${VERSION})" "${UPSTREAM}"  \
&& git merge "${UPSTREAM}" \
${nop}
