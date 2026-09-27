-- MariaDB 서비스 DB · 회원 단건 조회 (lambda/member 서비스 함수가 사용)
-- 바인드 파라미터: :member_id
SELECT member_id, username, email, asset
FROM member
WHERE member_id = :member_id;
